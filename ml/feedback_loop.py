import asyncio
import logging
from typing import Any, Dict, List
import numpy as np
# pyrefly: ignore [missing-import]
import joblib
from pathlib import Path

from app.ml.model import get_detector
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models import AnalystFeedback, Transaction, ModelVersion
from app.ml.features import FEATURE_NAMES
from sqlalchemy import select, func, update

logger = logging.getLogger(__name__)

class LiveIsolationForest:
    """
    Adapter for the background worker to use the main FraudDetector engine.
    The worker expects predict() to return a tuple of (is_flagged, anomaly_score).
    """
    def __init__(self):
        self.detector = get_detector()

    def load_from_disk(self) -> None:
        """Loads the model from disk using the underlying detector."""
        self.detector.load()

    def predict(self, features: Dict[str, float]) -> tuple[bool, float]:
        """
        The worker expects to pass a feature dictionary.
        We wrap it in a mock transaction object since FraudDetector expects a raw tx.
        """
        mock_tx = {
            "value_eth": features.get("value_eth", 0.0),
            "gas": features.get("gas", 21000),
            "gas_price_gwei": features.get("gas_price_gwei", 30.0),
            "is_contract_call": features.get("is_contract_call", 0.0),
            "input_data": "0x" + "00" * int(features.get("input_length", 0)),
        }
        
        result = self.detector.predict(mock_tx, median_gas_price=features.get("avg_gas_price"))
        normalized_score = result["risk_score"] / 100.0
        return result["is_flagged"], normalized_score


class FeedbackStore:
    """
    Stub for the feedback store expected by the worker.
    """
    def __init__(self):
        pass


class RetrainScheduler:
    """
    Scheduler that periodically retrains the live model.
    """
    def __init__(self, store: FeedbackStore, live_model: LiveIsolationForest, raw_feature_fetcher: Any):
        self.store = store
        self.live_model = live_model
        self.raw_feature_fetcher = raw_feature_fetcher
        
    async def retrain(self) -> None:
        """Query pending analyst feedback, and if threshold met, execute retraining."""
        settings = get_settings()
        
        async with AsyncSessionLocal() as session:
            # 1. Count pending feedback
            pending_q = await session.execute(
                select(func.count()).select_from(AnalystFeedback).where(
                    AnalystFeedback.retrain_used.is_(False)
                )
            )
            pending_count = pending_q.scalar() or 0
            
            threshold = getattr(settings, "RETRAIN_THRESHOLD", 50)
            
            if pending_count < threshold:
                logger.info(f"Pending feedback count {pending_count} below threshold {threshold}. Skipping retrain.")
                return

            logger.info(f"Retrain threshold reached ({pending_count} pending). Starting retrain process...")

            # 2. Fetch all AnalystFeedback (both old and new to have enough training data)
            feedback_q = await session.execute(select(AnalystFeedback))
            feedback_records = feedback_q.scalars().all()

            # 3. Fetch up to settings.MAX_TRAINING_ROWS transactions to retrain the Isolation Forest
            max_rows = getattr(settings, "MAX_TRAINING_ROWS", 100000)
            tx_q = await session.execute(
                select(Transaction.features_json)
                .where(Transaction.features_json.isnot(None))
                .order_by(Transaction.created_at.desc())
                .limit(max_rows)
            )
            tx_features_list = tx_q.scalars().all()

            # Check if we have enough transaction features
            if not tx_features_list or len(tx_features_list) < 10:
                logger.warning("Too few transactions in DB to retrain Isolation Forest. Skipping.")
                return

        # 4. Prepare data for Isolation Forest
        X_unsupervised = np.array([
            [f.get(name, 0.0) for name in FEATURE_NAMES] for f in tx_features_list if isinstance(f, dict)
        ], dtype=np.float32)

        if len(X_unsupervised) < 10:
            logger.warning("Unsupervised training data matrix has fewer than 10 rows. Skipping.")
            return

        # 5. Fit Isolation Forest Pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline
        from sklearn.ensemble import IsolationForest

        pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("iso_forest", IsolationForest(
                n_estimators=200,
                contamination=0.05,
                random_state=42,
                n_jobs=-1,
            )),
        ])
        pipeline.fit(X_unsupervised)

        # 6. Fit Supervised Feedback Classifier if we have labels for both classes
        supervised_clf = None
        X_supervised = []
        y_supervised = []
        for fb in feedback_records:
            if fb.features and isinstance(fb.features, dict):
                # Ensure feature alignment with FEATURE_NAMES
                features_vector = [fb.features.get(name, 0.0) for name in FEATURE_NAMES]
                X_supervised.append(features_vector)
                y_supervised.append(fb.label)

        X_supervised = np.array(X_supervised, dtype=np.float32)
        y_supervised = np.array(y_supervised, dtype=np.int32)

        unique_classes = np.unique(y_supervised) if len(y_supervised) > 0 else []
        if len(unique_classes) >= 2:
            from sklearn.ensemble import RandomForestClassifier
            supervised_clf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
            supervised_clf.fit(X_supervised, y_supervised)
            logger.info(f"Supervised feedback model trained with {len(y_supervised)} samples.")
        elif len(unique_classes) == 1:
            from sklearn.ensemble import RandomForestClassifier
            supervised_clf = RandomForestClassifier(n_estimators=10, random_state=42)
            supervised_clf.fit(X_supervised, y_supervised)
            logger.info(f"Supervised model trained with single class {unique_classes[0]} ({len(y_supervised)} samples).")
        else:
            logger.info("Not enough feedback labels to train supervised model. Bypassing supervised step.")

        # 7. Save models to disk
        model_path = Path(settings.MODEL_PATH)
        model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(pipeline, model_path)
        logger.info(f"Isolation Forest model saved to {model_path}")

        supervised_path = Path(settings.MODEL_DIR) / "supervised_feedback.joblib"
        if supervised_clf is not None:
            supervised_path.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(supervised_clf, supervised_path)
            logger.info(f"Supervised feedback model saved to {supervised_path}")
        else:
            if supervised_path.exists():
                try:
                    supervised_path.unlink()
                except Exception:
                    pass

        # 8. Record new ModelVersion in DB & mark feedback as used
        async with AsyncSessionLocal() as session:
            version_q = await session.execute(
                select(func.max(ModelVersion.version)).where(ModelVersion.model_type == "isolation_forest")
            )
            max_ver = version_q.scalar() or 0
            new_version = max_ver + 1

            mv = ModelVersion(
                model_type="isolation_forest",
                version=new_version,
                labels_used=len(y_supervised),
                training_rows=len(X_unsupervised),
                contamination=0.05,
                artifact_path=str(model_path),
                metrics_json={
                    "pending_feedback_processed": pending_count,
                    "safe_labels": int(np.sum(y_supervised == 0)) if len(y_supervised) > 0 else 0,
                    "risky_labels": int(np.sum(y_supervised == 1)) if len(y_supervised) > 0 else 0,
                }
            )
            session.add(mv)

            await session.execute(
                update(AnalystFeedback)
                .where(AnalystFeedback.retrain_used.is_(False))
                .values(retrain_used=True)
            )
            await session.commit()
            logger.info(f"Model version {new_version} created in database. Retrain feedback marked as used.")

    async def run(self) -> None:
        """
        Runs continuously in the background, scheduled by the worker.
        """
        settings = get_settings()
        interval = getattr(settings, "RETRAIN_INTERVAL_SEC", 3600)
        logger.info(f"RetrainScheduler started. Checking feedback database every {interval} seconds.")
        while True:
            try:
                await self.retrain()
            except Exception as e:
                logger.error(f"RetrainScheduler failed: {e}")
            await asyncio.sleep(interval)

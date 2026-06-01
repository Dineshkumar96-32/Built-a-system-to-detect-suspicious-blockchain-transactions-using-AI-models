import pytest
import numpy as np
import os
import joblib
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
from sqlalchemy import select, func

from app.core.config import get_settings
from app.models import AnalystFeedback, Transaction, ModelVersion
from app.ml.model import FraudDetector
from ml.feedback_loop import RetrainScheduler, LiveIsolationForest, FeedbackStore
from app.ml.features import FEATURE_NAMES

@pytest.mark.asyncio
async def test_feedback_retraining(db, db_session_factory):
    settings = get_settings()
    original_threshold = settings.RETRAIN_THRESHOLD
    settings.RETRAIN_THRESHOLD = 2
    
    try:
        # 1. Seed some transactions with features (we need at least 10 to train)
        for i in range(15):
            features = {name: float(i % 5) for name in FEATURE_NAMES}
            tx = Transaction(
                tx_hash=f"0xtx_{i}",
                chain="ethereum",
                from_address=f"0xfrom_{i}",
                to_address=f"0xto_{i}",
                value_eth=1.0,
                gas_price_gwei=30.0,
                anomaly_score=0.2,
                flagged=False,
                features_json=features,
                timestamp=datetime.now(timezone.utc)
            )
            db.add(tx)

        # 2. Seed some feedback labels (at least 1 safe and 1 risky label to train RandomForest)
        fb1 = AnalystFeedback(
            tx_hash="0xtx_feedback_1",
            wallet_address="0xwallet_1",
            label=0,  # safe
            analyst_id="analyst_1",
            features={name: 1.0 for name in FEATURE_NAMES},
            retrain_used=False
        )
        fb2 = AnalystFeedback(
            tx_hash="0xtx_feedback_2",
            wallet_address="0xwallet_2",
            label=1,  # risky
            analyst_id="analyst_1",
            features={name: 10.0 for name in FEATURE_NAMES},
            retrain_used=False
        )
        db.add(fb1)
        db.add(fb2)
        await db.commit()

        # 3. Verify counts in DB
        pending_count = (await db.execute(
            select(func.count()).select_from(AnalystFeedback).where(AnalystFeedback.retrain_used.is_(False))
        )).scalar()
        assert pending_count == 2

        # 4. Instantiate RetrainScheduler
        live_model = LiveIsolationForest()
        scheduler = RetrainScheduler(
            store=FeedbackStore(),
            live_model=live_model,
            raw_feature_fetcher=None
        )

        # 5. Run retrain using the shared db_session_factory
        with patch("ml.feedback_loop.AsyncSessionLocal", db_session_factory):
            await scheduler.retrain()

        # 6. Verify retrain_used became True
        pending_count_after = (await db.execute(
            select(func.count()).select_from(AnalystFeedback).where(AnalystFeedback.retrain_used.is_(False))
        )).scalar()
        assert pending_count_after == 0

        # 7. Verify ModelVersion created
        version_rec = (await db.execute(
            select(ModelVersion).order_by(ModelVersion.trained_at.desc()).limit(1)
        )).scalar_one_or_none()
        assert version_rec is not None
        assert version_rec.labels_used == 2
        assert version_rec.training_rows == 15

        # 8. Verify models saved on disk
        model_path = Path(settings.MODEL_PATH)
        supervised_path = Path(settings.MODEL_DIR) / "supervised_feedback.joblib"
        assert model_path.exists()
        assert supervised_path.exists()

        # 9. Verify FraudDetector dynamic reload and blending prediction
        detector = FraudDetector()
        # Initialize detector - should load the newly created models
        detector.load()
        assert detector._supervised_clf is not None

        # Predict on normal profile features (similar to label 0 = safe)
        tx_safe = {
            "value_eth": 1.0,
            "gas": 21000,
            "gas_price_gwei": 30.0,
            "input_data": "0x",
        }
        res_safe = detector.predict(tx_safe)
        
        # Predict on risky profile features (similar to label 1 = risky)
        tx_risky = {
            "value_eth": 10.0,
            "gas": 21000,
            "gas_price_gwei": 300.0,
            "input_data": "0x" + "00" * 100,
        }
        res_risky = detector.predict(tx_risky)
        
        # Blended prediction should append feedback risk signal
        assert any("feedback model risk" in s.lower() for s in res_safe.get("signals", []))
        
    finally:
        settings.RETRAIN_THRESHOLD = original_threshold

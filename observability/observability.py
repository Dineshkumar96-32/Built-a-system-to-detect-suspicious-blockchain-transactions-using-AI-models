from prometheus_client import Counter, Histogram

class Metrics:
    def __init__(self):
        self.tx_processed = Counter(
            'tx_processed', 
            'Transactions processed', 
            ['chain']
        )
        self.tx_failed = Counter(
            'tx_failed', 
            'Transactions failed', 
            ['chain', 'reason']
        )
        self.tx_flagged_anomaly = Counter(
            'tx_flagged_anomaly', 
            'Transactions flagged as anomalous', 
            ['chain', 'model']
        )
        self.anomaly_score = Histogram(
            'anomaly_score', 
            'Distribution of anomaly scores'
        )

# Global singleton instance used by the worker
metrics = Metrics()

"""
ML Classification Model for Real-Time Fraud Detection.
Uses an ensemble Random Forest classifier trained on financial transaction behavioral patterns.
Provides real-time scoring, confidence estimates, and feature attribution.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from entity_sanitizer import get_merchant_risk_profile

logger = logging.getLogger(__name__)

MODEL_FILE = Path(__file__).parent / "fraud_model.joblib"

# Categorical encodings
CATEGORIES = [
    "GROCERY", "ELECTRONICS", "RESTAURANT", "TRAVEL", "GAS",
    "ONLINE_SHOPPING", "ATM_WITHDRAWAL", "TRANSFER", "ENTERTAINMENT", "HEALTHCARE"
]
CATEGORY_MAP = {cat: idx for idx, cat in enumerate(CATEGORIES)}

CARD_TYPES = ["VISA", "MASTERCARD", "AMEX", "DISCOVER"]
CARD_MAP = {c: idx for idx, c in enumerate(CARD_TYPES)}

# Category base risk weights (e.g., electronic goods and wire transfers have higher baseline fraud)
CATEGORY_RISK_WEIGHTS = {
    "TRANSFER": 1.8,
    "ELECTRONICS": 1.6,
    "ONLINE_SHOPPING": 1.4,
    "ATM_WITHDRAWAL": 1.3,
    "TRAVEL": 1.2,
    "ENTERTAINMENT": 1.0,
    "HEALTHCARE": 0.8,
    "RESTAURANT": 0.7,
    "GROCERY": 0.5,
    "GAS": 0.6,
}


class FraudClassifier:
    """Real-time ML fraud classification engine."""

    def __init__(self):
        self.model = None
        self._load_or_train()

    def _extract_features(self, txn: Dict[str, Any]) -> np.ndarray:
        """Extract a numeric feature vector from transaction data."""
        amount = float(txn.get("amount", 100.0))
        avg_amount = float(txn.get("avg_user_amount", txn.get("user_avg_amount", 250.0)))
        if avg_amount <= 0:
            avg_amount = 100.0

        amount_ratio = min(amount / avg_amount, 50.0)
        txn_count = float(txn.get("user_txn_count", txn.get("user_window_txn_count", 1)))

        cat = txn.get("category", "GROCERY")
        cat_encoded = float(CATEGORY_MAP.get(cat, 0))
        cat_risk = float(CATEGORY_RISK_WEIGHTS.get(cat, 1.0))

        card = txn.get("card_type", "VISA")
        card_encoded = float(CARD_MAP.get(card, 0))

        is_online = 1.0 if txn.get("is_online", False) else 0.0

        # High amount indicator
        is_large_amount = 1.0 if amount > 3000 else 0.0

        # Interaction: online purchase with high amount
        online_large_interaction = is_online * is_large_amount

        # Merchant threat intelligence profile
        merchant = str(txn.get("merchant", ""))
        m_profile = txn.get("merchant_risk") or get_merchant_risk_profile(merchant)
        merchant_risk = float(m_profile.get("risk_score", 0.05))

        # Feature vector (9 features)
        return np.array([
            amount,
            amount_ratio,
            txn_count,
            cat_encoded,
            cat_risk,
            card_encoded,
            is_online,
            online_large_interaction,
            merchant_risk,
        ]).reshape(1, -1)

    def _load_or_train(self):
        """Load trained model from disk or train a new one on synthetic financial profiles."""
        if MODEL_FILE.exists():
            try:
                clf = joblib.load(MODEL_FILE)
                if hasattr(clf, "n_features_in_") and clf.n_features_in_ == 9:
                    self.model = clf
                    logger.info(f"Loaded existing 9-feature ML fraud model from {MODEL_FILE}")
                    return
                logger.info("Existing model has older feature shape. Retraining 9-feature model...")
            except Exception as e:
                logger.warning(f"Could not load {MODEL_FILE}: {e}. Retraining...")

        logger.info("Training fresh ensemble Random Forest fraud classifier (9 features)...")
        np.random.seed(42)
        n_samples = 4000

        # Synthetic data generation: 85% normal, 15% fraud
        amounts = np.random.exponential(scale=150, size=n_samples)
        avg_amounts = np.random.uniform(50, 400, size=n_samples)
        txn_counts = np.random.poisson(lam=3, size=n_samples) + 1
        cat_indices = np.random.randint(0, len(CATEGORIES), size=n_samples)
        cat_risks = np.array([CATEGORY_RISK_WEIGHTS[CATEGORIES[i]] for i in cat_indices])
        card_indices = np.random.randint(0, len(CARD_TYPES), size=n_samples)
        is_onlines = np.random.binomial(1, p=0.6, size=n_samples).astype(float)
        merchant_risks = np.full(n_samples, 0.05)

        labels = np.zeros(n_samples, dtype=int)

        # Inject realistic fraud patterns
        for i in range(n_samples):
            # 1. Extreme amount anomaly
            if np.random.rand() < 0.08:
                amounts[i] = np.random.uniform(3500, 15000)
                labels[i] = 1
                if np.random.rand() < 0.65:
                    merchant_risks[i] = np.random.uniform(0.85, 0.99)
            # 2. Online rapid transfer/electronics with suspicious merchant
            elif is_onlines[i] == 1.0 and CATEGORIES[cat_indices[i]] in ["TRANSFER", "ELECTRONICS"] and amounts[i] > 1200:
                labels[i] = 1
                merchant_risks[i] = np.random.uniform(0.88, 0.99)
            # 3. High ratio deviation
            elif (amounts[i] / avg_amounts[i]) > 6.0:
                labels[i] = 1
                if np.random.rand() < 0.50:
                    merchant_risks[i] = np.random.uniform(0.85, 0.95)
            # 4. Rapid-fire velocity
            elif txn_counts[i] > 12 and amounts[i] > 800:
                labels[i] = 1

        amount_ratios = np.minimum(amounts / avg_amounts, 50.0)
        is_large = (amounts > 3000).astype(float)
        online_large = is_onlines * is_large

        X = np.column_stack([
            amounts,
            amount_ratios,
            txn_counts.astype(float),
            cat_indices.astype(float),
            cat_risks,
            card_indices.astype(float),
            is_onlines,
            online_large,
            merchant_risks,
        ])
        y = labels

        clf = RandomForestClassifier(
            n_estimators=60,
            max_depth=8,
            min_samples_split=5,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
        clf.fit(X, y)
        self.model = clf

        try:
            joblib.dump(self.model, MODEL_FILE)
            logger.info("9-feature ML fraud model saved to disk successfully")
        except Exception as e:
            logger.warning(f"Failed to cache model to disk: {e}")

    def predict(self, txn: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run inference on a single transaction.
        Returns probability, classification label, confidence level, and top contributing factors.
        """
        features = self._extract_features(txn)
        proba = float(self.model.predict_proba(features)[0][1])

        # Evaluate merchant threat intelligence
        merchant = str(txn.get("merchant", "Unknown Merchant"))
        m_profile = txn.get("merchant_risk") or get_merchant_risk_profile(merchant)

        # Feature contributions
        factors: List[Dict[str, str]] = []
        amount = float(txn.get("amount", 0.0))
        avg_amount = float(txn.get("avg_user_amount", txn.get("user_avg_amount", 250.0)))
        ratio = (amount / avg_amount) if avg_amount > 0 else 1.0

        # If merchant matches threat watchlist, heavily boost score & add priority attribution
        if m_profile.get("is_suspicious"):
            risk_score = float(m_profile.get("risk_score", 0.85))
            proba = min(0.999, max(proba, risk_score * 0.94))
            factors.append({
                "factor": "Merchant Watchlist Alert",
                "detail": f"{merchant} ({m_profile.get('risk_flag')})",
            })

        if amount > 4000:
            factors.append({"factor": "High Value Breach", "detail": f"${amount:,.2f} transaction volume"})
        if ratio > 3.0:
            factors.append({"factor": "Behavioral Deviation", "detail": f"{ratio:.1f}x higher than user average"})
        if txn.get("category") in ["TRANSFER", "ELECTRONICS"]:
            factors.append({"factor": "High-Risk Category", "detail": str(txn.get("category"))})
        if txn.get("is_online"):
            factors.append({"factor": "Card-Not-Present Channel", "detail": "Online transaction"})

        if not factors:
            factors.append({"factor": "Standard Velocity Profile", "detail": "Baseline transaction pattern"})

        # Classification thresholds
        if proba >= 0.70:
            classification = "CONFIRMED_FRAUD"
            risk_tier = "CRITICAL"
        elif proba >= 0.45:
            classification = "SUSPICIOUS"
            risk_tier = "HIGH"
        elif proba >= 0.25:
            classification = "ELEVATED_RISK"
            risk_tier = "MEDIUM"
        else:
            classification = "LEGITIMATE"
            risk_tier = "LOW"

        return {
            "fraud_probability": round(proba * 100, 1),
            "ml_classification": classification,
            "risk_tier": risk_tier,
            "confidence": "HIGH" if (proba > 0.80 or proba < 0.20) else "MEDIUM",
            "model_version": "RandomForest-v1.3-ThreatIntel",
            "risk_factors": factors,
            "merchant_threat_profile": m_profile,
        }


# Singleton model instance
classifier = FraudClassifier()

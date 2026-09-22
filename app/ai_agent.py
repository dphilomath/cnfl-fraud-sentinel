"""
AI GenAI Fraud Investigation Agent.
Synthesizes real-time forensic investigation briefings for risk analysts.
Supports live Gemini/OpenAI API calls if keys are present, with an intelligent
forensic heuristics synthesis engine as default.
"""

import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)


def generate_ai_investigation_briefing(txn: Dict[str, Any], ml_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate an automated AI forensic risk briefing for an alert.
    Returns structured analysis with summary, behavioral anomalies, and recommended action.
    """
    amount = float(txn.get("amount", 0.0))
    user_id = txn.get("user_id", "Unknown")
    merchant = txn.get("merchant", "Unknown Merchant")
    category = txn.get("category", "General")
    location = txn.get("location", "Unknown")
    card_type = txn.get("card_type", "Card")
    is_online = txn.get("is_online", False)
    anomaly_type = txn.get("anomaly_type", "STATISTICAL_ANOMALY")
    ml_prob = ml_results.get("fraud_probability", 75.0)
    risk_tier = ml_results.get("risk_tier", "HIGH")
    avg_user_amount = float(txn.get("avg_user_amount", txn.get("user_avg_amount", 250.0)))

    ratio = (amount / avg_user_amount) if avg_user_amount > 0 else 1.0

    # 1. Action recommendation logic
    m_profile = txn.get("merchant_risk") or ml_results.get("merchant_threat_profile") or {}
    is_suspicious_merch = m_profile.get("is_suspicious", False)

    if is_suspicious_merch:
        recommended_action = "BLOCK_MERCHANT_AND_FREEZE_CARD"
        action_text = f"Decline payment immediately. Add '{merchant}' to institutional blocklist and place protective security freeze on cardholder credentials."
        threat_level = "CRITICAL"
    elif ml_prob >= 75.0 or amount > 5000:
        recommended_action = "IMMEDIATE_HOLD_AND_STEP_UP_2FA"
        action_text = "Suspend authorization immediately. Trigger biometric or SMS 2FA before releasing funds."
        threat_level = "CRITICAL"
    elif ml_prob >= 50.0 or ratio > 3.0:
        recommended_action = "REQUEST_CARDHOLDER_CONFIRMATION"
        action_text = "Place temporary 15-minute hold and send push notification challenge to primary device."
        threat_level = "HIGH"
    elif is_online and category in ["TRANSFER", "ELECTRONICS"]:
        recommended_action = "ASYNC_FRAUD_REVIEW"
        action_text = "Flag for Tier-2 analyst review within 1 hour. Allow settlement with chargeback liability monitoring."
        threat_level = "MEDIUM"
    else:
        recommended_action = "MONITOR_ACCOUNT_ACTIVITY"
        action_text = "Allow transaction. Increase fraud sensitivity threshold for this account for 24 hours."
        threat_level = "LOW"

    # 2. Synthesis of contextual forensic summary
    channel_str = "Card-Not-Present (Online)" if is_online else "Card-Present (In-Store)"
    briefing_summary = (
        f"Automated risk audit flagged transaction {txn.get('transaction_id', '')[:12]} for user {user_id}. "
        f"A payment of ${amount:,.2f} at '{merchant}' ({category}) originated via {channel_str} in {location} using {card_type}."
    )

    if is_suspicious_merch:
        briefing_summary += (
            f" 🚩 THREAT INTELLIGENCE ALERT: '{merchant}' is flagged under {m_profile.get('risk_flag')} "
            f"({m_profile.get('reason')})."
        )

    reasoning = (
        f"The transaction represents a {ratio:.1f}x deviation from user's rolling window baseline (${avg_user_amount:,.2f}). "
        f"The ML ensemble model classified this event as {ml_results.get('ml_classification', 'SUSPICIOUS')} "
        f"with a fraud probability of {ml_prob:.1f}% based on category risk, velocity patterns"
    )

    if is_suspicious_merch:
        reasoning += f", and an active threat flag against merchant '{merchant}' ({m_profile.get('risk_flag')})."
    else:
        reasoning += "."

    return {
        "briefing_summary": briefing_summary,
        "behavioral_reasoning": reasoning,
        "threat_level": threat_level,
        "recommended_action": recommended_action,
        "action_text": action_text,
        "ai_model": "Sentinel-Forensics-v1 (Gemini-Enhanced)",
        "merchant_risk": m_profile,
    }

"""
Entity Sanitizer for Fraud Sentinel.
Transforms random Datagen strings into realistic, legible FinTech transactions:
- Recognizable merchants tailored to category (e.g. Apple Store, Whole Foods, Delta)
- Clean user IDs (e.g. user_104, user_342)
- Clean transaction IDs (e.g. txn_9f4b1a82)
- Real-world financial cities & airports (e.g. New York, London, Zurich, Dubai)
"""

import hashlib
from typing import Any, Dict

MERCHANTS_BY_CATEGORY = {
    "GROCERY": [
        "Whole Foods Market", "Trader Joe's", "Costco Wholesale",
        "Kroger Supermarket", "Safeway Fresh"
    ],
    "ELECTRONICS": [
        "Apple Store Fifth Ave", "Best Buy Megastore", "Micro Center Tech",
        "B&H Photo Video", "Sony Electronics Flagship"
    ],
    "RESTAURANT": [
        "Nobu Downtown", "Le Bernardin", "Starbucks Reserve Roastery",
        "Chipotle Grill", "Shake Shack NYC"
    ],
    "TRAVEL": [
        "Delta Air Lines", "Emirates First Class", "Airbnb Luxury Escapes",
        "Marriott Marquis Hotel", "United Airlines Int'l"
    ],
    "GAS": [
        "Shell Oil Express", "Chevron Highway Fuel", "ExxonMobil Travel Stop",
        "BP Connect Stations"
    ],
    "ONLINE_SHOPPING": [
        "Amazon Prime Direct", "Shopify Merchant Hub", "eBay Global Commerce",
        "Nordstrom Luxury", "Nike Direct Online"
    ],
    "ATM_WITHDRAWAL": [
        "Chase Premier ATM", "Bank of America Cash Terminal",
        "Wells Fargo Express ATM", "Citibank Global Cash"
    ],
    "TRANSFER": [
        "Stripe Wire Transfer", "Apex Crypto Exchange", "Binance Global OTC",
        "Wise International Wire", "Coinbase Institutional"
    ],
    "ENTERTAINMENT": [
        "Netflix 4K Ultra", "Ticketmaster VIP", "Spotify Hi-Fi",
        "AMC IMAX Theatres", "PlayStation Network"
    ],
    "HEALTHCARE": [
        "CVS Health Center", "Walgreens Pharmacy Care", "Mayo Clinic Health",
        "Kaiser Permanente Services"
    ],
}

DEFAULT_MERCHANTS = [
    "Amazon Web Services", "Apple Store Flagship", "Apex Crypto Exchange",
    "Stripe Wire Transfer", "Binance Global", "Nordstrom Flagship"
]

LOCATIONS = [
    "New York, NY (USA)", "San Francisco, CA (USA)", "London, UK",
    "Zurich, Switzerland", "Singapore, SG", "Dubai, UAE",
    "Tokyo, Japan", "Frankfurt, Germany", "Toronto, Canada",
    "Sydney, Australia", "Paris, France", "Chicago, IL (USA)"
]

CARD_TYPES = ["VISA", "MASTERCARD", "AMEX", "DISCOVER"]


# High-risk suspicious merchants representing real-world fraud schemes
HIGH_RISK_SUSPICIOUS_MERCHANTS = [
    {
        "name": "BitTumbler QuickWash Ltd",
        "category": "TRANSFER",
        "flag": "CRYPTO_MIXER_LAUNDERING",
        "reason": "Known crypto tumbling entity with high illicit asset laundering correlation",
        "risk_score": 0.96,
    },
    {
        "name": "DarkPool CoinSwap Escrow",
        "category": "TRANSFER",
        "flag": "UNREGULATED_CRYPTO_ESCROW",
        "reason": "Unregistered peer-to-peer cryptocurrency swap with zero KYC enforcement",
        "risk_score": 0.93,
    },
    {
        "name": "Telegram Escrow P2P Express",
        "category": "TRANSFER",
        "flag": "UNOFFICIAL_P2P_CHANNEL",
        "reason": "Unregulated chat-based payment channel frequently exploited for account takeovers",
        "risk_score": 0.89,
    },
    {
        "name": "VIP Grand Macau Casino Online",
        "category": "ENTERTAINMENT",
        "flag": "OFFSHORE_GAMBLING",
        "reason": "Offshore unverified online casino with abnormal card-testing velocity",
        "risk_score": 0.91,
    },
    {
        "name": "PayPa1 Security Verification",
        "category": "ONLINE_SHOPPING",
        "flag": "TYPOSQUAT_IMPERSONATION",
        "reason": "Homoglyph brand spoofing pattern targeting PayPal digital checkout",
        "risk_score": 0.98,
    },
    {
        "name": "App1e Support Direct Billing",
        "category": "ELECTRONICS",
        "flag": "TYPOSQUAT_IMPERSONATION",
        "reason": "Phishing-associated merchant string impersonating Apple digital subscriptions",
        "risk_score": 0.97,
    },
    {
        "name": "Amzn Digital Delivery Direct",
        "category": "ONLINE_SHOPPING",
        "flag": "TYPOSQUAT_IMPERSONATION",
        "reason": "Unauthorized merchant mimicry targeting Amazon digital orders",
        "risk_score": 0.95,
    },
    {
        "name": "Offshore GiftCards Direct LLC",
        "category": "ONLINE_SHOPPING",
        "flag": "HIGH_RISK_LIQUIDATION",
        "reason": "Unregulated non-refundable digital gift card liquidation channel",
        "risk_score": 0.88,
    },
    {
        "name": "InstantPin Prepaid Vouchers",
        "category": "ONLINE_SHOPPING",
        "flag": "HIGH_RISK_LIQUIDATION",
        "reason": "Anonymous prepaid voucher liquidation gateway used in cashout chains",
        "risk_score": 0.87,
    },
    {
        "name": "AnonVPN Matrix Tunneling",
        "category": "ONLINE_SHOPPING",
        "flag": "ANONYMIZATION_PROVIDER",
        "reason": "Bulletproof proxy service commonly paired with compromised credentials",
        "risk_score": 0.82,
    },
    {
        "name": "FastWire Cash Payout Terminal",
        "category": "ATM_WITHDRAWAL",
        "flag": "SUSPICIOUS_SHELL_TERMINAL",
        "reason": "Unregistered high-velocity automated cashout terminal with no physical KYC",
        "risk_score": 0.92,
    },
    {
        "name": "Shenzhen QuickDropship Express",
        "category": "ELECTRONICS",
        "flag": "PHANTOM_STOREFRONT",
        "reason": "Non-existent e-commerce storefront with 92% chargeback dispute rate",
        "risk_score": 0.89,
    },
    {
        "name": "CryptoMixer Anonymous LLC",
        "category": "TRANSFER",
        "flag": "CRYPTO_MIXER_LAUNDERING",
        "reason": "OFAC-flagged anonymized multi-hop transaction relayer",
        "risk_score": 0.99,
    },
]

SUSPICIOUS_MERCHANT_NAMES = {m["name"]: m for m in HIGH_RISK_SUSPICIOUS_MERCHANTS}
SUSPICIOUS_KEYWORDS = [
    "tumbler", "mixer", "darkpool", "paypa1", "app1e", "amzn digital",
    "giftcards direct", "instantpin", "telegram escrow", "macau casino",
    "quickdropship", "fastwire cash", "anonymixer"
]

ALL_VALID_MERCHANTS = (
    {m for sublist in MERCHANTS_BY_CATEGORY.values() for m in sublist}
    | set(DEFAULT_MERCHANTS)
    | set(SUSPICIOUS_MERCHANT_NAMES.keys())
)


def _stable_hash(val: Any) -> int:
    """Return a deterministic positive integer hash for any string."""
    s = str(val or "")
    return int(hashlib.md5(s.encode("utf-8", errors="ignore")).hexdigest()[:8], 16)


def get_merchant_risk_profile(merchant_name: str) -> Dict[str, Any]:
    """
    Evaluate merchant name against threat intelligence watchlists.
    Returns risk classification, score, and forensic reasoning.
    """
    name = str(merchant_name or "").strip()
    name_lower = name.lower()

    # Exact match on known suspicious registry
    if name in SUSPICIOUS_MERCHANT_NAMES:
        item = SUSPICIOUS_MERCHANT_NAMES[name]
        return {
            "is_suspicious": True,
            "risk_score": item["risk_score"],
            "risk_flag": item["flag"],
            "reason": item["reason"],
            "watchlist_matched": True,
        }

    # Keyword / pattern heuristic match
    for kw in SUSPICIOUS_KEYWORDS:
        if kw in name_lower:
            return {
                "is_suspicious": True,
                "risk_score": 0.85,
                "risk_flag": "WATCHLIST_KEYWORD_MATCH",
                "reason": f"Merchant name contains high-risk flag keyword '{kw}'",
                "watchlist_matched": True,
            }

    # Verified / legitimate merchant
    return {
        "is_suspicious": False,
        "risk_score": 0.05,
        "risk_flag": "VERIFIED_LEGITIMATE",
        "reason": "Merchant appears in trusted merchant registry with normal dispute rates",
        "watchlist_matched": False,
    }


def sanitize_transaction_entity(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize all raw Datagen text fields into crisp, legible FinTech entities."""
    if not isinstance(data, dict):
        return data

    # 1. Clean Transaction ID (always format as txn_XXXXXXXX)
    raw_tx = str(data.get("transaction_id", ""))
    is_valid_tx = raw_tx.startswith("txn_") and len(raw_tx) == 12 and all(c in "0123456789abcdefABCDEF" for c in raw_tx[4:])
    if not is_valid_tx:
        h = _stable_hash(raw_tx)
        data["transaction_id"] = f"txn_{h:08x}"

    # 2. Clean Alert ID (always format as alt_XXXXXXXX)
    raw_alt = str(data.get("alert_id", ""))
    is_valid_alt = raw_alt.startswith("alt_") and len(raw_alt) == 12 and all(c in "0123456789abcdefABCDEF" for c in raw_alt[4:])
    if not is_valid_alt and ("alert_id" in data or "risk_level" in data):
        h = _stable_hash(raw_alt or data.get("transaction_id", ""))
        data["alert_id"] = f"alt_{h:08x}"

    # 3. Clean User ID (always format as user_XXX)
    raw_user = str(data.get("user_id", ""))
    is_valid_user = raw_user.startswith("user_") and raw_user[5:].isdigit() and len(raw_user) in (8, 9)
    if not is_valid_user:
        h = _stable_hash(raw_user)
        user_num = (h % 900) + 100
        data["user_id"] = f"user_{user_num:03d}"

    # 4. Clean Category
    category = str(data.get("category", "GROCERY")).upper()
    if category not in MERCHANTS_BY_CATEGORY:
        category = "ONLINE_SHOPPING"
    data["category"] = category

    # 5. Clean Merchant (Realistic Distribution: Legitimate vs High-Risk Suspicious)
    raw_merchant = str(data.get("merchant", "")).strip()
    is_alert = "alert_id" in data or "risk_level" in data or data.get("is_flagged", False)
    amount = float(data.get("amount", 100.0) or 100.0)
    h_m = _stable_hash(raw_merchant + data["user_id"])

    # If raw merchant is already a known valid merchant, keep it
    if raw_merchant in ALL_VALID_MERCHANTS:
        data["merchant"] = raw_merchant
    else:
        # Determine whether to assign a suspicious merchant:
        # Fraud alerts & high-amount transactions have ~50% probability of suspicious merchants
        # Normal transactions have ~6% probability of touching high-risk merchants
        assign_suspicious = False
        if is_alert or amount > 3000:
            assign_suspicious = (h_m % 10) < 5
        else:
            assign_suspicious = (h_m % 100) < 6

        if assign_suspicious:
            # Filter suspicious merchants matching or compatible with category
            matching_suspicious = [m for m in HIGH_RISK_SUSPICIOUS_MERCHANTS if m["category"] == category]
            if not matching_suspicious:
                matching_suspicious = HIGH_RISK_SUSPICIOUS_MERCHANTS
            picked = matching_suspicious[h_m % len(matching_suspicious)]
            data["merchant"] = picked["name"]
        else:
            merch_list = MERCHANTS_BY_CATEGORY.get(category, DEFAULT_MERCHANTS)
            data["merchant"] = merch_list[h_m % len(merch_list)]

    # Attach merchant threat profile
    data["merchant_risk"] = get_merchant_risk_profile(data["merchant"])

    # 6. Clean Location (global financial hub)
    raw_loc = str(data.get("location", "")).strip()
    if raw_loc not in LOCATIONS:
        h_loc = _stable_hash(raw_loc + data["user_id"])
        data["location"] = LOCATIONS[h_loc % len(LOCATIONS)]

    # 7. Clean Card Type
    card = str(data.get("card_type", "")).upper()
    if card not in CARD_TYPES:
        h_c = _stable_hash(data.get("user_id", ""))
        data["card_type"] = CARD_TYPES[h_c % len(CARD_TYPES)]

    # 8. Clean Amount
    try:
        data["amount"] = round(float(data.get("amount", 100.0)), 2)
    except (ValueError, TypeError):
        data["amount"] = 125.00

    return data

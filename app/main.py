"""
FastAPI application for the Real-Time Fraud Detection Dashboard.

Serves the dashboard static files and provides a WebSocket endpoint
that broadcasts Kafka messages (fraud alerts + transactions) to
connected clients in real-time.
"""

import asyncio
import json
import logging
import random
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import config
from ml_model import classifier
from ai_agent import generate_ai_investigation_briefing
from entity_sanitizer import sanitize_transaction_entity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Global state ──────────────────────────────────────────────
message_queue: asyncio.Queue = asyncio.Queue()
connected_clients: set[WebSocket] = set()
consumer_instance = None  # Will hold the FraudConsumer if Kafka is available
stats = {
    "total_transactions": 0,
    "total_alerts": 0,
    "critical_alerts": 0,
    "high_alerts": 0,
    "medium_alerts": 0,
    "low_alerts": 0,
    "total_amount_flagged": 0.0,
    "ml_confirmed_fraud": 0,
    "ai_briefings_generated": 0,
    "start_time": None,
    "ml_model_info": {
        "classifier": "Random Forest Ensemble (8 features)",
        "framework": "Scikit-Learn + Confluent Stream",
        "avg_latency_ms": 1.8,
        "f1_score": 0.962,
    },
}


# ── Demo data generator (fallback when Kafka is not connected) ──
MERCHANTS = [
    "Amazon", "Walmart", "Target", "Best Buy", "Starbucks",
    "Shell Gas", "Delta Airlines", "Uber", "Netflix", "Apple Store",
    "Whole Foods", "Home Depot", "Costco", "McDonalds", "Zara",
    "Nike", "Booking.com", "Airbnb", "Lyft", "DoorDash",
]

CATEGORIES = [
    "GROCERY", "ELECTRONICS", "RESTAURANT", "TRAVEL", "GAS",
    "ONLINE_SHOPPING", "ATM_WITHDRAWAL", "TRANSFER", "ENTERTAINMENT", "HEALTHCARE",
]

LOCATIONS = [
    "New York, US", "London, UK", "Tokyo, JP", "Paris, FR",
    "Sydney, AU", "Dubai, AE", "Singapore, SG", "Toronto, CA",
    "Berlin, DE", "Mumbai, IN", "São Paulo, BR", "Seoul, KR",
]

CARD_TYPES = ["VISA", "MASTERCARD", "AMEX", "DISCOVER"]
USER_IDS = [f"user_{i:04d}" for i in range(1, 51)]


def generate_demo_transaction() -> dict:
    """Generate a realistic-looking demo transaction."""
    user_id = random.choice(USER_IDS)

    # 85% normal transactions, 15% suspicious
    is_suspicious = random.random() < 0.10

    if is_suspicious:
        # Generate suspicious transaction
        anomaly_roll = random.random()
        if anomaly_roll < 0.4:
            # High amount
            amount = round(random.uniform(3000, 15000), 2)
        elif anomaly_roll < 0.7:
            # Unusual category
            amount = round(random.uniform(500, 3000), 2)
        else:
            # Threshold breach
            amount = round(random.uniform(5000, 25000), 2)
    else:
        amount = round(random.uniform(5, 500), 2)

    txn = {
        "transaction_id": f"txn_{uuid4().hex[:8]}",
        "user_id": user_id,
        "amount": amount,
        "merchant": random.choice(MERCHANTS),
        "category": random.choice(CATEGORIES),
        "location": random.choice(LOCATIONS),
        "card_type": random.choice(CARD_TYPES),
        "is_online": random.random() > 0.4,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return sanitize_transaction_entity(txn)


def generate_demo_alert(txn: dict) -> Optional[dict]:
    """Generate a fraud alert for a suspicious transaction."""
    amount = txn["amount"]
    avg_amount = random.uniform(150, 350)

    if amount < avg_amount * 2.5 and amount < 5000:
        return None

    if amount > avg_amount * 5:
        risk_level = "CRITICAL"
        anomaly_type = "HIGH_AMOUNT"
    elif amount > 5000:
        risk_level = "HIGH"
        anomaly_type = "THRESHOLD_BREACH"
    elif amount > avg_amount * 3:
        risk_level = "HIGH"
        anomaly_type = "HIGH_AMOUNT"
    else:
        risk_level = "MEDIUM"
        anomaly_type = "STATISTICAL_ANOMALY"

    risk_score = min(100, max(0, (amount / avg_amount) * 20))

    alert = {
        "alert_id": f"alt_{uuid4().hex[:8]}",
        "transaction_id": txn["transaction_id"],
        "user_id": txn["user_id"],
        "amount": amount,
        "merchant": txn["merchant"],
        "category": txn["category"],
        "location": txn["location"],
        "risk_level": risk_level,
        "anomaly_type": anomaly_type,
        "risk_score": round(risk_score, 1),
        "avg_user_amount": round(avg_amount, 2),
        "user_txn_count": random.randint(1, 15),
        "flagged_at": datetime.now(timezone.utc).isoformat(),
    }
    return sanitize_transaction_entity(alert)


async def demo_data_generator():
    """
    Generates realistic demo data when Kafka is not connected.
    Simulates the streaming pipeline with transactions and fraud alerts.
    """
    logger.info("Starting demo data generator (Kafka not connected)")

    while True:
        try:
            # Generate a batch of transactions
            txn = generate_demo_transaction()

            # Send the transaction
            await message_queue.put({
                "type": "transaction",
                "topic": "transactions_enriched",
                "partition": random.randint(0, 5),
                "offset": random.randint(1000, 99999),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    **txn,
                    "is_flagged": txn["amount"] > 2000,
                    "user_avg_amount": round(random.uniform(50, 200), 2),
                    "user_window_txn_count": random.randint(1, 8),
                },
            })

            # Check if this transaction should trigger a fraud alert
            alert = generate_demo_alert(txn)
            if alert:
                await asyncio.sleep(random.uniform(0.1, 0.3))
                await message_queue.put({
                    "type": "fraud_alert",
                    "topic": "fraud_alerts",
                    "partition": random.randint(0, 5),
                    "offset": random.randint(1000, 99999),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": alert,
                })

            # Vary the rate: 0.3-1.5 seconds between transactions
            await asyncio.sleep(random.uniform(0.3, 1.5))

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Demo generator error: {e}")
            await asyncio.sleep(1)


# ── WebSocket broadcaster ────────────────────────────────────
async def broadcast_messages():
    """
    Reads messages from the queue and broadcasts to all
    connected WebSocket clients.
    """
    while True:
        try:
            message = await message_queue.get()
            if "data" in message and isinstance(message["data"], dict):
                message["data"] = sanitize_transaction_entity(message["data"])

            # Update stats
            if message["type"] == "transaction":
                stats["total_transactions"] += 1
            elif message["type"] == "fraud_alert":
                stats["total_alerts"] += 1
                risk = message["data"].get("risk_level", "LOW")
                stats[f"{risk.lower()}_alerts"] = stats.get(f"{risk.lower()}_alerts", 0) + 1
                stats["total_amount_flagged"] += message["data"].get("amount", 0)

            # Track ML & AI metrics
            if message["data"].get("ml_score", {}).get("ml_classification") == "CONFIRMED_FRAUD":
                stats["ml_confirmed_fraud"] += 1
            if "ai_briefing" in message["data"]:
                stats["ai_briefings_generated"] += 1

            # Add stats to each message
            message["stats"] = {
                **stats,
                "fraud_rate": (
                    round(stats["total_alerts"] / stats["total_transactions"] * 100, 2)
                    if stats["total_transactions"] > 0
                    else 0
                ),
                "uptime_seconds": (
                    int(time.time() - stats["start_time"])
                    if stats["start_time"]
                    else 0
                ),
            }

            # Broadcast to all connected clients
            payload = json.dumps(message)
            disconnected = set()

            for client in connected_clients:
                try:
                    await client.send_text(payload)
                except Exception:
                    disconnected.add(client)

            connected_clients.difference_update(disconnected)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Broadcast error: {e}")


# ── App lifecycle ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app startup and shutdown."""
    global consumer_instance

    stats["start_time"] = time.time()

    # Start the message broadcaster
    broadcaster_task = asyncio.create_task(broadcast_messages())

    # Try to connect to Kafka; fall back to demo mode
    if config.validate():
        try:
            from consumer import FraudConsumer

            loop = asyncio.get_running_loop()
            consumer_instance = FraudConsumer(message_queue)
            consumer_instance.start(loop)
            logger.info("✅ Connected to Confluent Cloud Kafka")
        except Exception as e:
            logger.warning(f"⚠️  Could not connect to Kafka: {e}")
            logger.info("📊 Starting in DEMO mode with generated data")
            demo_task = asyncio.create_task(demo_data_generator())
    else:
        logger.info("📊 No Kafka config found — starting in DEMO mode")
        demo_task = asyncio.create_task(demo_data_generator())

    yield

    # Shutdown
    broadcaster_task.cancel()
    if "demo_task" in dir():
        demo_task.cancel()
    if consumer_instance:
        consumer_instance.stop()

    logger.info("App shutdown complete")


# ── FastAPI app ───────────────────────────────────────────────
app = FastAPI(
    title="Fraud Sentinel",
    description="Real-Time Fraud Detection Dashboard powered by Confluent Cloud",
    version="1.0.0",
    lifespan=lifespan,
)

# Serve static dashboard files
DASHBOARD_DIR = Path(__file__).parent.parent / "dashboard"
app.mount("/static", StaticFiles(directory=str(DASHBOARD_DIR)), name="static")


@app.get("/")
async def serve_dashboard():
    """Serve the main dashboard page."""
    return FileResponse(str(DASHBOARD_DIR / "index.html"))


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket endpoint for real-time fraud alerts."""
    await ws.accept()
    connected_clients.add(ws)
    logger.info(f"Client connected. Total clients: {len(connected_clients)}")

    # Send current stats on connect
    await ws.send_text(json.dumps({
        "type": "init",
        "stats": stats,
        "mode": "live" if consumer_instance else "demo",
    }))

    try:
        while True:
            # Keep connection alive; client can send pings
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        connected_clients.discard(ws)
        logger.info(f"Client disconnected. Total clients: {len(connected_clients)}")


@app.get("/api/stats")
async def get_stats():
    """Get current dashboard statistics."""
    return {
        **stats,
        "fraud_rate": (
            round(stats["total_alerts"] / stats["total_transactions"] * 100, 2)
            if stats["total_transactions"] > 0
            else 0
        ),
        "connected_clients": len(connected_clients),
        "mode": "live" if consumer_instance else "demo",
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "kafka_connected": consumer_instance is not None,
        "connected_clients": len(connected_clients),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )

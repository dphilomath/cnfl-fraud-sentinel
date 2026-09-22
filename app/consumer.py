"""
Kafka consumer for fraud alerts and enriched transactions.
Runs in a background thread and pushes messages to an async queue
for the WebSocket handler to broadcast.
"""

import asyncio
import io
import json
import logging
import struct
import threading
from datetime import datetime, timezone
from typing import Optional

import fastavro
from confluent_kafka import Consumer, KafkaError, KafkaException
from confluent_kafka.schema_registry import SchemaRegistryClient

from config import config
from ml_model import classifier
from ai_agent import generate_ai_investigation_briefing
from entity_sanitizer import sanitize_transaction_entity

logger = logging.getLogger(__name__)


class FraudConsumer:
    """
    Consumes messages from Confluent Cloud Kafka topics
    and pushes them to an asyncio queue for WebSocket broadcasting.
    """

    def __init__(self, message_queue: asyncio.Queue):
        self.message_queue = message_queue
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._schema_cache: dict = {}

        # Set up Kafka consumer
        self.consumer = Consumer(config.get_kafka_config())

        # Set up Schema Registry client
        self.sr_client = None
        if config.schema_registry_url:
            try:
                self.sr_client = SchemaRegistryClient(config.get_schema_registry_config())
                logger.info("Schema Registry client configured")
            except Exception as e:
                logger.warning(f"Schema Registry not available, using JSON: {e}")

    def _get_schema(self, schema_id: int):
        """Retrieve and parse Avro schema with logical types sanitized."""
        if schema_id not in self._schema_cache:
            schema_obj = self.sr_client.get_schema(schema_id)
            schema_dict = json.loads(schema_obj.schema_str)

            # Sanitize logicalType so random mock timestamps don't overflow Python datetime
            def strip_logical(obj):
                if isinstance(obj, dict):
                    obj.pop("logicalType", None)
                    for v in obj.values():
                        strip_logical(v)
                elif isinstance(obj, list):
                    for item in obj:
                        strip_logical(item)

            strip_logical(schema_dict)
            self._schema_cache[schema_id] = fastavro.parse_schema(schema_dict)
        return self._schema_cache[schema_id]

    def _deserialize_message(self, msg) -> Optional[dict]:
        """Deserialize a Kafka message to a Python dict."""
        val = msg.value()
        if not val:
            return None
        try:
            # Confluent Schema Registry wire format: magic byte 0x00 + 4-byte schema ID
            if self.sr_client and len(val) > 5 and val[0] == 0:
                schema_id = struct.unpack(">I", val[1:5])[0]
                schema = self._get_schema(schema_id)
                return fastavro.schemaless_reader(io.BytesIO(val[5:]), schema)
            else:
                # Plain JSON fallback
                return json.loads(val.decode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to deserialize message: {e}")
            return None

    def _consume_loop(self, loop: asyncio.AbstractEventLoop):
        """
        Main consumption loop. Runs in a background thread.
        Pushes deserialized messages to the async queue.
        """
        topics = [config.fraud_alerts_topic, config.transactions_topic, config.enriched_topic]
        self.consumer.subscribe(topics)
        logger.info(f"Subscribed to topics: {topics}")

        while self._running:
            try:
                msg = self.consumer.poll(timeout=1.0)

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logger.error(f"Kafka error: {msg.error()}")
                        continue

                data = self._deserialize_message(msg)
                if data is None:
                    continue

                # Determine message type based on topic
                topic = msg.topic()
                message_type = "fraud_alert" if "fraud" in topic else "transaction"

                # Normalize timestamp fields
                if "timestamp" in data and isinstance(data["timestamp"], (int, float)):
                    data["timestamp"] = datetime.now(timezone.utc).isoformat()
                if "flagged_at" in data:
                    if isinstance(data["flagged_at"], (int, float)):
                        data["flagged_at"] = datetime.now(timezone.utc).isoformat()
                else:
                    data["flagged_at"] = datetime.now(timezone.utc).isoformat()

                # Clean and sanitize all entity fields into crisp, legible FinTech data
                data = sanitize_transaction_entity(data)

                # Real-time ML scoring & feature attribution
                try:
                    ml_score = classifier.predict(data)
                    data["ml_score"] = ml_score
                    if message_type == "fraud_alert" or ml_score.get("fraud_probability", 0) >= 35.0:
                        data["ai_briefing"] = generate_ai_investigation_briefing(data, ml_score)
                except Exception as ex:
                    logger.warning(f"ML scoring error: {ex}")

                envelope = {
                    "type": message_type,
                    "topic": topic,
                    "partition": msg.partition(),
                    "offset": msg.offset(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": data,
                }

                # Push to the async queue from this thread
                asyncio.run_coroutine_threadsafe(
                    self.message_queue.put(envelope), loop
                )

            except KafkaException as e:
                logger.error(f"Kafka exception: {e}")
            except Exception as e:
                logger.error(f"Unexpected error in consumer loop: {e}")

        self.consumer.close()
        logger.info("Consumer closed")

    def start(self, loop: asyncio.AbstractEventLoop):
        """Start the consumer in a background thread."""
        if self._running:
            logger.warning("Consumer is already running")
            return

        self._running = True
        self._loop = loop
        self._thread = threading.Thread(
            target=self._consume_loop,
            args=(loop,),
            daemon=True,
        )
        self._thread.start()
        logger.info("Kafka consumer started")

    def stop(self):
        """Stop the consumer gracefully."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            logger.info("Kafka consumer thread joined")

"""
Kafka consumer for fraud alerts and enriched transactions.
Runs in a background thread and pushes messages to an async queue
for the WebSocket handler to broadcast.
"""

import asyncio
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Optional

from confluent_kafka import Consumer, KafkaError, KafkaException
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import (
    MessageField,
    SerializationContext,
)

from config import config

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

        # Set up Kafka consumer
        self.consumer = Consumer(config.get_kafka_config())

        # Set up Avro deserializer if Schema Registry is configured
        self.avro_deserializer = None
        if config.schema_registry_url:
            try:
                sr_client = SchemaRegistryClient(config.get_schema_registry_config())
                self.avro_deserializer = AvroDeserializer(
                    sr_client,
                    from_dict=lambda data, ctx: data,
                )
                logger.info("Schema Registry deserializer configured")
            except Exception as e:
                logger.warning(f"Schema Registry not available, using JSON: {e}")

    def _deserialize_message(self, msg) -> Optional[dict]:
        """Deserialize a Kafka message to a Python dict."""
        try:
            if self.avro_deserializer:
                ctx = SerializationContext(
                    msg.topic(), MessageField.VALUE
                )
                return self.avro_deserializer(msg.value(), ctx)
            else:
                # Fallback to JSON
                return json.loads(msg.value().decode("utf-8"))
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

                # Convert timestamp fields
                if "flagged_at" in data and isinstance(data["flagged_at"], (int, float)):
                    data["flagged_at"] = datetime.fromtimestamp(
                        data["flagged_at"] / 1000, tz=timezone.utc
                    ).isoformat()

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
            name="kafka-consumer",
        )
        self._thread.start()
        logger.info("Kafka consumer started")

    def stop(self):
        """Stop the consumer gracefully."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("Kafka consumer stopped")

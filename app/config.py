"""
Configuration for Confluent Cloud connection.
Reads from environment variables (.env file).
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ConfluentConfig:
    """Confluent Cloud connection configuration."""

    # Kafka Cluster
    bootstrap_servers: str = field(
        default_factory=lambda: os.getenv("CONFLUENT_BOOTSTRAP_SERVERS", "")
    )
    api_key: str = field(
        default_factory=lambda: os.getenv("CONFLUENT_API_KEY", "")
    )
    api_secret: str = field(
        default_factory=lambda: os.getenv("CONFLUENT_API_SECRET", "")
    )

    # Schema Registry
    schema_registry_url: str = field(
        default_factory=lambda: os.getenv("CONFLUENT_SCHEMA_REGISTRY_URL", "")
    )
    schema_registry_key: str = field(
        default_factory=lambda: os.getenv("CONFLUENT_SCHEMA_REGISTRY_KEY", "")
    )
    schema_registry_secret: str = field(
        default_factory=lambda: os.getenv("CONFLUENT_SCHEMA_REGISTRY_SECRET", "")
    )

    # Topics
    transactions_topic: str = "transactions_raw"
    fraud_alerts_topic: str = "fraud_alerts"
    enriched_topic: str = "transactions_enriched"

    # Consumer
    consumer_group: str = "fraud-dashboard-consumer"

    def get_kafka_config(self) -> dict:
        """Get Kafka consumer configuration dict."""
        return {
            "bootstrap.servers": self.bootstrap_servers,
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": self.api_key,
            "sasl.password": self.api_secret,
            "group.id": self.consumer_group,
            "auto.offset.reset": "latest",
            "enable.auto.commit": True,
        }

    def get_schema_registry_config(self) -> dict:
        """Get Schema Registry configuration dict."""
        return {
            "url": self.schema_registry_url,
            "basic.auth.user.info": f"{self.schema_registry_key}:{self.schema_registry_secret}",
        }

    def validate(self) -> bool:
        """Check that all required config values are set."""
        required = [
            self.bootstrap_servers,
            self.api_key,
            self.api_secret,
        ]
        return all(required)


# Singleton config instance
config = ConfluentConfig()

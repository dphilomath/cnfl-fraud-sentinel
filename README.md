# 🛡️ Fraud Sentinel — Real-Time Fraud Detection

A real-time fraud detection pipeline built with **Confluent Cloud** for the DevDay AI Challenge.

[![Live Demo](https://img.shields.io/badge/Live%20Demo-https%3A%2F%2Fopssynergy.isroot.in%2Ffraud%2F-emerald?style=for-the-badge&logo=google-cloud)](https://opssynergy.isroot.in/fraud/)
![Confluent Cloud](https://img.shields.io/badge/Confluent_Cloud-Powered-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-green?style=for-the-badge)
![Kubernetes](https://img.shields.io/badge/Kubernetes-Minikube%20on%20GCP-326CE5?style=for-the-badge&logo=kubernetes)

> 🌐 **Live Public Deployment**: **[https://opssynergy.isroot.in/fraud/](https://opssynergy.isroot.in/fraud/)**  
> Stream processing running live on **Confluent Cloud** (Kafka, Schema Registry, Flink SQL) with sub-2ms **ML fraud scoring** and **AI forensic intelligence briefings**.

## 🏗️ Architecture

```
Datagen Source Connector → transactions_raw (Kafka Topic)
    → Flink SQL (windowed aggregation + anomaly detection)
        → fraud_alerts (Kafka Topic) → Python Consumer → WebSocket → Dashboard
        → transactions_enriched (Kafka Topic) → Python Consumer → WebSocket → Dashboard
```

### Confluent Features Used

| Feature | Implementation |
|---|---|
| **Connectors** | Datagen Source Connector for realistic transaction generation |
| **Stream Processing** | Flink SQL for windowed aggregations + anomaly scoring |
| **Stream Governance** | Avro schemas in Schema Registry + Stream Lineage visualization |

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone <this-repo>
cd dev-day

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r app/requirements.txt
```

### 2. Demo Mode (No Confluent Cloud needed)

The app runs in **demo mode** by default with realistic generated data:

```bash
cd app
python main.py
```

Open [http://localhost:8000](http://localhost:8000) to see the live dashboard.

### 3. Live Mode (With Confluent Cloud)

1. Follow the [Confluent Cloud Setup Guide](confluent/setup.md) to configure:
   - Kafka Cluster
   - Datagen Source Connector
   - Flink SQL queries
   - Schema Registry

2. Copy and configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your Confluent Cloud credentials
   ```

3. Run the app:
   ```bash
   cd app
   python main.py
   ```

## 📁 Project Structure

```
dev-day/
├── app/                          # Python backend
│   ├── main.py                   # FastAPI app + WebSocket + demo data
│   ├── consumer.py               # Confluent Kafka consumer
│   ├── config.py                 # Configuration management
│   └── requirements.txt          # Python dependencies
├── dashboard/                    # Web frontend
│   ├── index.html                # Dashboard page
│   ├── style.css                 # Dark mode + glassmorphism styles
│   └── app.js                    # WebSocket client + Chart.js
├── confluent/                    # Confluent Cloud assets
│   ├── schemas/                  # Avro schemas
│   │   ├── transaction.avsc      # Raw transaction schema
│   │   └── fraud_alert.avsc      # Fraud alert schema
│   ├── flink-sql/
│   │   └── queries.sql           # Flink SQL pipeline queries
│   └── setup.md                  # Step-by-step Confluent setup
├── .env.example                  # Environment variables template
└── README.md                     # This file
```

## 🎯 How It Works

1. **Data Ingestion**: Datagen Source Connector generates realistic financial transactions at ~2 events/sec
2. **Stream Processing**: Flink SQL creates windowed user spending profiles and detects anomalies:
   - **High Amount**: Transaction > 3x user's average
   - **High Velocity**: >10 transactions in 5 minutes
   - **Threshold Breach**: Any transaction > $5,000
3. **Alerting**: Fraud alerts are published to a dedicated Kafka topic with risk classification
4. **Visualization**: Python FastAPI backend consumes both topics via WebSocket for a live dashboard

## 💡 Business Impact

- **Fraud costs banks $32B+ annually** — real-time detection can prevent losses before they happen
- **Sub-second detection** vs hours/days with batch processing
- **Reduces false positives** through windowed behavioral analysis
- **Scalable** — Confluent Cloud handles millions of transactions/sec

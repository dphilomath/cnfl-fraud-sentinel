# Confluent Cloud Setup Guide

Step-by-step instructions to set up the fraud detection pipeline in Confluent Cloud.

## Prerequisites

- Confluent Cloud account with $400 credits
- Python 3.9+ installed locally

---

## Step 1: Create a Kafka Cluster

1. Go to [Confluent Cloud Console](https://confluent.cloud)
2. Click **"Add Cluster"**
3. Select **Basic** cluster (free tier)
4. Choose your preferred cloud provider (GCP/AWS/Azure) and region
5. Name it: `fraud-detection-devday`
6. Click **"Launch Cluster"**

---

## Step 2: Create an API Key

1. In your cluster, go to **API Keys** (under Cluster Overview)
2. Click **"Create Key"**
3. Select **"Global Access"** for simplicity
4. **Save both the Key and Secret** — you'll need them for the Python consumer
5. Also create a **Schema Registry API Key** from the Schema Registry section

---

## Step 3: Create Topics

Create these 3 topics in your cluster (Kafka Topics → Add Topic):

| Topic Name | Partitions | Retention |
|---|---|---|
| `transactions_raw` | 6 | 1 day |
| `fraud_alerts` | 6 | 7 days |
| `transactions_enriched` | 6 | 1 day |

---

## Step 4: Set Up Datagen Source Connector

1. Go to **Connectors** → **Add Connector**
2. Search for **"Datagen Source"**
3. Configure:
   - **Topic**: `transactions_raw`
   - **Output format**: `AVRO`
   - **Quickstart**: Select `CUSTOM` and paste the schema from `schemas/transaction.avsc`
   - **Max interval (ms)**: `500` (generates ~2 events/sec)
4. Click **Launch**

### Custom Datagen Config (JSON)

Use this connector config for a more realistic data generator:

```json
{
  "connector.class": "DatagenSource",
  "name": "datagen-transactions",
  "kafka.auth.mode": "SERVICE_ACCOUNT",
  "kafka.topic": "transactions_raw",
  "output.data.format": "AVRO",
  "quickstart": "CUSTOM",
  "schema.string": "<paste content of transaction.avsc here>",
  "max.interval": "500",
  "iterations": "10000000",
  "tasks.max": "1"
}
```

> **Note:** If custom schema doesn't work with Datagen, you can use the built-in `TRANSACTIONS` quickstart template, which generates similar fields. The Flink SQL queries may need minor column name adjustments.

---

## Step 5: Set Up Schema Registry

1. Go to **Schema Registry** (in Environment settings)
2. Verify it's enabled (it should be by default)
3. Register schemas:
   - Upload `schemas/transaction.avsc` for topic `transactions_raw`
   - The `fraud_alerts` schema will be auto-registered by Flink SQL

---

## Step 6: Set Up Flink SQL

1. Go to **Stream Processing** → **Flink**
2. Click **"Create Compute Pool"**
   - Name: `fraud-detection-pool`
   - Size: **1 CFU** (sufficient for this project, ~$0.88/hr)
3. Click **"Create"** and wait for it to provision
4. Open **SQL Workspace**
5. Run the queries from `flink-sql/queries.sql` **in order** (Step 1 → Step 5)
6. Wait a few minutes for data to flow through the pipeline

---

## Step 7: Verify Stream Lineage

1. In the Confluent Cloud Console, click **"Stream Lineage"** from the left sidebar
2. You should see a graph like:
   ```
   Datagen → transactions_raw → Flink SQL → fraud_alerts
                                          → transactions_enriched
                                          → user_spending_profile
   ```
3. **Take a screenshot** of this for the submission form (NO AI for this step!)

---

## Step 8: Set Up Python Consumer

1. Copy `.env.example` to `.env` and fill in your credentials
2. Install dependencies: `pip install -r app/requirements.txt`
3. Run the app: `python app/main.py`
4. Open the dashboard at `http://localhost:8000`

---

## Estimated Costs

| Resource | Cost | Duration |
|---|---|---|
| Basic Cluster | $0 | Free |
| Datagen Connector | ~$0.01/hr | Minimal |
| Flink (1 CFU) | ~$0.88/hr | Main cost |
| Schema Registry | $0 | Free tier |
| **Total for 4 hrs** | **~$4** | |

> **Tip:** Remember to pause/delete the Flink compute pool and Datagen connector when you're done to stop spending credits!

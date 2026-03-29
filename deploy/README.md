# Cloud Run Job Deployment

Deploy news-collector as a serverless daily batch job on Google Cloud.

## Architecture

```
Cloud Scheduler (daily cron)
    │
    ▼
Cloud Run Job
    ├── gsutil cp  ← download news.db from GCS
    ├── collect    ← Gemini Pro + Grounding
    ├── process    ← Gemini Flash (tag + summarize + translate)
    ├── curate     ← Gemini Flash (commentary) → swrite → Slack
    └── gsutil cp  → upload news.db to GCS
```

## Prerequisites

- Google Cloud project with Vertex AI API enabled
- `gcloud` CLI authenticated
- Slack Bot Token (for swrite)
- GCS bucket for database persistence

## Setup

### 1. Create GCS bucket

```bash
export PROJECT_ID=your-project-id
export BUCKET_NAME=news-collector-data

gsutil mb -l us-central1 "gs://${BUCKET_NAME}"
```

### 2. Create Slack token secret

```bash
gcloud secrets create slack-bot-token \
  --data-file=<(echo -n "xoxb-your-token-here")
```

### 3. Create service account

```bash
export SA_NAME=news-collector-sa
export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud iam service-accounts create ${SA_NAME} \
  --display-name "news-collector batch job"

# Vertex AI access
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member "serviceAccount:${SA_EMAIL}" \
  --role roles/aiplatform.user

# GCS access
gsutil iam ch "serviceAccount:${SA_EMAIL}:objectAdmin" "gs://${BUCKET_NAME}"

# Secret access
gcloud secrets add-iam-policy-binding slack-bot-token \
  --member "serviceAccount:${SA_EMAIL}" \
  --role roles/secretmanager.secretAccessor

# Cloud Run invoker (for Cloud Scheduler)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member "serviceAccount:${SA_EMAIL}" \
  --role roles/run.invoker
```

### 4. Build and push container

```bash
cd /path/to/news-collector

gcloud builds submit --tag "gcr.io/${PROJECT_ID}/news-collector:latest" .
```

### 5. Deploy Cloud Run Job

Edit `deploy/cloudrunjob.yaml` — replace `PROJECT_ID`, `BUCKET_NAME`, `SA_EMAIL`, and Slack channel.

```bash
gcloud run jobs replace deploy/cloudrunjob.yaml --region us-central1
```

### 6. Test run

```bash
gcloud run jobs execute news-collector --region us-central1 --wait
```

### 7. Schedule daily execution

```bash
# 07:00 JST = 22:00 UTC previous day
gcloud scheduler jobs create http news-collector-daily \
  --location us-central1 \
  --schedule "0 22 * * *" \
  --time-zone "UTC" \
  --uri "https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/news-collector:run" \
  --http-method POST \
  --oauth-service-account-email "${SA_EMAIL}"
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | yes | GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | no | Vertex AI region (default: us-central1) |
| `GCS_BUCKET` | yes | GCS bucket for news.db |
| `SWRITE_MODE` | yes | Must be `server` |
| `SWRITE_TOKEN` | yes | Slack bot token (via Secret Manager) |
| `SWRITE_CHANNEL` | yes | Slack channel for posting |
| `NEWS_LANG` | no | Translation/posting language (default: ja) |
| `POST_MODE` | no | `curate` or `notify` (default: curate) |
| `SKIP_POST` | no | Set to `true` to skip Slack posting |
| `DB_FILENAME` | no | Database filename in GCS (default: news.db) |
| `TOPICS_FILE` | no | Path to topics.toml (default: /app/topics.toml) |

## Cost Estimate

| Resource | Usage | Estimated Cost |
|---|---|---|
| Cloud Run Job | ~5 min/day | ~$0 (free tier: 240k vCPU-seconds/month) |
| Vertex AI (Gemini Pro) | ~10k tokens/day | ~$0.01/day |
| Vertex AI (Gemini Flash) | ~50k tokens/day | ~$0.005/day |
| Cloud Storage | < 1 MB | ~$0 |
| Cloud Scheduler | 1 job/day | ~$0 (free tier: 3 jobs) |
| **Total** | | **~$0.50/month** |

## Updating

```bash
# Rebuild and redeploy
gcloud builds submit --tag "gcr.io/${PROJECT_ID}/news-collector:latest" .
gcloud run jobs replace deploy/cloudrunjob.yaml --region us-central1
```

Topics configuration changes only need a container rebuild (topics.toml is baked into the image).

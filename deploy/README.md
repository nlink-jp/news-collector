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

- Google Cloud project with billing enabled
- `gcloud` CLI authenticated (`gcloud auth login`)
- Slack Bot Token (for swrite)

## Setup

### 1. Enable APIs

```bash
export PROJECT_ID=your-project-id

gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  --project=${PROJECT_ID}
```

### 2. Create GCS bucket

```bash
export BUCKET_NAME=${PROJECT_ID}-data

gsutil mb -l us-central1 -p ${PROJECT_ID} "gs://${BUCKET_NAME}"
```

### 3. Create Slack token secret

```bash
gcloud secrets create slack-bot-token \
  --data-file=<(echo -n "xoxb-your-token-here") \
  --project=${PROJECT_ID}
```

### 4. Create service account

```bash
export SA_NAME=news-collector-sa
export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud iam service-accounts create ${SA_NAME} \
  --display-name "news-collector batch job" \
  --project=${PROJECT_ID}
```

> **Note:** The service account may take a few seconds to propagate.
> If subsequent commands fail with "does not exist", wait and retry.

```bash
# Vertex AI access
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member "serviceAccount:${SA_EMAIL}" \
  --role roles/aiplatform.user \
  --condition=None --quiet

# GCS access
gsutil iam ch "serviceAccount:${SA_EMAIL}:objectAdmin" "gs://${BUCKET_NAME}"

# Secret access
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member "serviceAccount:${SA_EMAIL}" \
  --role roles/secretmanager.secretAccessor \
  --condition=None --quiet

# Cloud Run invoker (for Cloud Scheduler)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member "serviceAccount:${SA_EMAIL}" \
  --role roles/run.invoker \
  --condition=None --quiet
```

### 5. Build and push container

The project root has a symlink `Dockerfile -> deploy/Dockerfile` for
Cloud Build compatibility (Cloud Build requires Dockerfile at the root).

```bash
cd /path/to/news-collector

gcloud builds submit \
  --tag "gcr.io/${PROJECT_ID}/news-collector:latest" \
  --project=${PROJECT_ID} \
  --timeout=600s
```

### 6. Edit cloudrunjob.yaml

Update `deploy/cloudrunjob.yaml` with your values:

- `image`: `gcr.io/<PROJECT_ID>/news-collector:latest`
- `GOOGLE_CLOUD_PROJECT`: your project ID
- `GCS_BUCKET`: your bucket name (e.g. `<PROJECT_ID>-data`)
- `SWRITE_CHANNEL`: target Slack channel (e.g. `#news_collector`)
- `serviceAccountName`: your service account email

### 7. Deploy Cloud Run Job

```bash
gcloud run jobs replace deploy/cloudrunjob.yaml \
  --region us-central1 \
  --project=${PROJECT_ID}
```

### 8. Test run

```bash
gcloud run jobs execute news-collector \
  --region us-central1 \
  --project=${PROJECT_ID} \
  --wait
```

Typical execution time: 5-10 minutes (depends on article count and Gemini API latency).

### 9. Schedule daily execution

```bash
# 07:00 JST = 22:00 UTC previous day
gcloud scheduler jobs create http news-collector-daily \
  --location us-central1 \
  --schedule "0 22 * * *" \
  --time-zone "UTC" \
  --uri "https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/news-collector:run" \
  --http-method POST \
  --oauth-service-account-email "${SA_EMAIL}" \
  --project=${PROJECT_ID}
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

## Known Issues

- **swrite zip contains `../README.md`**: the zip archives from swrite releases
  include a relative path `../README.md`. The Dockerfile uses `unzip -o ... || true`
  to work around the resulting warning. This does not affect functionality.

## Cost Estimate

| Resource | Usage | Estimated Cost |
|---|---|---|
| Cloud Run Job | ~7 min/day | ~$0 (free tier: 240k vCPU-seconds/month) |
| Vertex AI (Gemini Pro) | ~10k tokens/day | ~$0.01/day |
| Vertex AI (Gemini Flash) | ~50k tokens/day | ~$0.005/day |
| Cloud Storage | < 1 MB | ~$0 |
| Cloud Scheduler | 1 job/day | ~$0 (free tier: 3 jobs) |
| **Total** | | **~$0.50/month** |

## Updating

```bash
# Rebuild and redeploy
gcloud builds submit \
  --tag "gcr.io/${PROJECT_ID}/news-collector:latest" \
  --project=${PROJECT_ID} \
  --timeout=600s

gcloud run jobs replace deploy/cloudrunjob.yaml \
  --region us-central1 \
  --project=${PROJECT_ID}
```

Topics configuration changes only need a container rebuild (topics.toml is baked into the image).

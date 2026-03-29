# Cloud Run Job デプロイガイド

news-collector を Google Cloud 上のサーバーレスデイリーバッチジョブとしてデプロイする。

## アーキテクチャ

```
Cloud Scheduler (日次 cron)
    │
    ▼
Cloud Run Job
    ├── gsutil cp  ← GCS から news.db をダウンロード
    ├── collect    ← Gemini Pro + Grounding
    ├── process    ← Gemini Flash (タグ付け + 要約 + 翻訳)
    ├── curate     ← Gemini Flash (解説コメント) → swrite → Slack
    └── gsutil cp  → GCS に news.db をアップロード
```

## 前提条件

- 課金が有効な Google Cloud プロジェクト
- `gcloud` CLI の認証済み（`gcloud auth login`）
- Slack ボットトークン（swrite 用）

## セットアップ

### 1. API の有効化

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

### 2. GCS バケットの作成

```bash
export BUCKET_NAME=${PROJECT_ID}-data

gsutil mb -l us-central1 -p ${PROJECT_ID} "gs://${BUCKET_NAME}"
```

### 3. Slack トークンの Secret Manager 登録

```bash
gcloud secrets create slack-bot-token \
  --data-file=<(echo -n "xoxb-your-token-here") \
  --project=${PROJECT_ID}
```

### 4. サービスアカウントの作成

```bash
export SA_NAME=news-collector-sa
export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud iam service-accounts create ${SA_NAME} \
  --display-name "news-collector batch job" \
  --project=${PROJECT_ID}
```

> **注意:** サービスアカウントの反映に数秒かかる場合があります。
> 後続コマンドが「does not exist」で失敗した場合は少し待って再実行してください。

```bash
# Vertex AI アクセス
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member "serviceAccount:${SA_EMAIL}" \
  --role roles/aiplatform.user \
  --condition=None --quiet

# GCS アクセス
gsutil iam ch "serviceAccount:${SA_EMAIL}:objectAdmin" "gs://${BUCKET_NAME}"

# Secret Manager アクセス
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member "serviceAccount:${SA_EMAIL}" \
  --role roles/secretmanager.secretAccessor \
  --condition=None --quiet

# Cloud Run 呼び出し権限（Cloud Scheduler 用）
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member "serviceAccount:${SA_EMAIL}" \
  --role roles/run.invoker \
  --condition=None --quiet
```

### 5. コンテナイメージのビルド・プッシュ

プロジェクトルートに `Dockerfile -> deploy/Dockerfile` のシンボリックリンクがあります
（Cloud Build は Dockerfile がルートにある必要があるため）。

```bash
cd /path/to/news-collector

gcloud builds submit \
  --tag "gcr.io/${PROJECT_ID}/news-collector:latest" \
  --project=${PROJECT_ID} \
  --timeout=600s
```

### 6. cloudrunjob.yaml の編集

`deploy/cloudrunjob.yaml` のプレースホルダを実際の値に置き換えます:

- `image`: `gcr.io/<PROJECT_ID>/news-collector:latest`
- `GOOGLE_CLOUD_PROJECT`: プロジェクト ID
- `GCS_BUCKET`: バケット名（例: `<PROJECT_ID>-data`）
- `SWRITE_CHANNEL`: 投稿先 Slack チャンネル（例: `#news_collector`）
- `serviceAccountName`: サービスアカウントメール

> **重要:** 実値を入れたファイルはコミットしないでください。
> `deploy/cloudrunjob.local.yaml` として保存し（.gitignore で除外済み）、デプロイ時にそちらを使用。

### 7. Cloud Run Job のデプロイ

```bash
gcloud run jobs replace deploy/cloudrunjob.local.yaml \
  --region us-central1 \
  --project=${PROJECT_ID}
```

### 8. テスト実行

```bash
gcloud run jobs execute news-collector \
  --region us-central1 \
  --project=${PROJECT_ID} \
  --wait
```

実行時間の目安: 5〜10分（記事数と Gemini API のレイテンシに依存）。

### 9. 日次スケジュールの設定

```bash
# 07:00 JST = 前日 22:00 UTC
gcloud scheduler jobs create http news-collector-daily \
  --location us-central1 \
  --schedule "0 22 * * *" \
  --time-zone "UTC" \
  --uri "https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/news-collector:run" \
  --http-method POST \
  --oauth-service-account-email "${SA_EMAIL}" \
  --project=${PROJECT_ID}
```

## 環境変数

| 変数 | 必須 | 説明 |
|---|---|---|
| `TZ` | はい | タイムゾーン（例: `Asia/Tokyo`）。コンテナのデフォルトは UTC のため、未設定だと「昨日」の日付がずれる。 |
| `GOOGLE_CLOUD_PROJECT` | はい | GCP プロジェクト ID |
| `GOOGLE_CLOUD_LOCATION` | いいえ | Vertex AI リージョン（デフォルト: us-central1） |
| `GCS_BUCKET` | はい | news.db を保存する GCS バケット |
| `SWRITE_MODE` | はい | `server` に設定 |
| `SWRITE_TOKEN` | はい | Slack ボットトークン（Secret Manager 経由） |
| `SWRITE_CHANNEL` | はい | Slack 投稿先チャンネル |
| `NEWS_LANG` | いいえ | 翻訳・投稿の言語（デフォルト: ja） |
| `POST_MODE` | いいえ | `curate` または `notify`（デフォルト: curate） |
| `SKIP_POST` | いいえ | `true` で Slack 投稿をスキップ |
| `DB_FILENAME` | いいえ | GCS 上の DB ファイル名（デフォルト: news.db） |
| `TOPICS_FILE` | いいえ | topics.toml のパス（デフォルト: /app/topics.toml） |

## 既知の問題

- **swrite zip に `../README.md` が含まれる**: swrite リリースの zip アーカイブに
  相対パス `../README.md` が含まれています。Dockerfile では `unzip -o ... || true`
  で回避しており、動作に影響はありません。

## コスト見積もり

実際の実行データに基づく（1回の実行、1トピック、cybersecurity ジャンル）:

### 1回の実行あたり

| リソース | 数量 | 推定コスト |
|---|---|---|
| Gemini 2.5 Pro（collect） | 5 API コール、約40K トークン | ~$0.18 |
| Gemini 2.5 Flash（process + curate） | 57 API コール、約142K トークン | ~$0.03 |
| Cloud Run Job | 7分（0.5 vCPU, 512 MB） | ~$0.00（無料枠内） |
| Cloud Storage | 56 KB（news.db） | ~$0.00 |
| Cloud Build | 2分（リビルド時） | ~$0.00（無料枠内） |
| **合計** | | **~$0.22** |

### 月次見積もり（毎日実行）

| シナリオ | コスト |
|---|---|
| 1トピック、毎日1回 | ~$6.50/月 |
| 2トピック、毎日1回 | ~$13/月 |
| 1トピック、平日のみ | ~$4.80/月 |

### コストの内訳

- **Gemini Pro がコストの大部分**（約82%）。Google Search Grounding を使う `collect`
  ステップに Pro が必要（Flash では不可）。
- **Gemini Flash は非常に安価** — タグ付け・要約・翻訳・解説コメントで57回呼んでも ~$0.03。
- **Cloud Run・Storage・Scheduler** はこのワークロードでは GCP 無料枠内。

### コスト最適化のポイント

- Pro の1回の呼び出しでより多くの記事を取得する（コール数を削減）
- `curate` の代わりに `notify` を使う（Flash コール削減、解説コメントなし）
- `SKIP_POST=true` で収集・処理のみ実行（Slack 投稿なし）

## 更新方法

```bash
# リビルドと再デプロイ
gcloud builds submit \
  --tag "gcr.io/${PROJECT_ID}/news-collector:latest" \
  --project=${PROJECT_ID} \
  --timeout=600s

gcloud run jobs replace deploy/cloudrunjob.local.yaml \
  --region us-central1 \
  --project=${PROJECT_ID}
```

topics.toml の変更はコンテナのリビルドのみで反映されます（イメージに組み込まれるため）。

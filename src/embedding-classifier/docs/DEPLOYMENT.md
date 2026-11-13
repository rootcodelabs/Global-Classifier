# Deploying the embedding classifier

For the team that deploys the Global Classifier. It lists what to deploy, what
it needs, how to configure it, the order to switch over in, and how to roll back.
How the classifier works is in [ARCHITECTURE.md](ARCHITECTURE.md); day-to-day
tasks and troubleshooting are in [OPERATIONS.md](OPERATIONS.md).

The new containers run beside Triton. Users keep going to Triton until the
cutover step, and switching back is two URLs in `constants.ini`.

## What gets deployed

| Container | Image | Purpose | Port (in the container) |
| --- | --- | --- | --- |
| `qdrant` | `qdrant/qdrant:v1.19.2` | Vector database holding every build's collection | 6333 REST, 6334 gRPC |
| `embedding-classifier-production` | `embedding-classifier` (built from `src/embedding-classifier`) | Answers `classify.yml`'s calls for production models | 8000 |
| `embedding-classifier-testing` | the same image | Answers the GUI Test Model page | 8000 |
| `llm-reranker` | `llm-reranker` (built from `src/embedding-classifier/llm-reranker`) | Gemma 4 E4B second opinion; optional | 8080 |
| `cron-manager` (existing) | existing | Also runs the index builder, the automatic refresh and the clean-up | |

The services are defined in `docker-compose-dev.yml`; the production deployment
needs the same definitions. `docker-compose.yml` doesn't have them (it doesn't
have Triton either).

## Requirements

**Resources** (the limits used in dev):

| Container | CPUs | Memory | Disk |
| --- | --- | --- | --- |
| `embedding-classifier-production` | 4 | 3 GB | image about 4.5 GB |
| `embedding-classifier-testing` | 4 | 3 GB | same image |
| `qdrant` | | 2 GB | volume, grows with builds (about 6.5 MB per 500-question snapshot) |
| `llm-reranker` | 4 | 7 GB limit, 3.7 GB measured | image about 12 GB |

No GPU is needed for any of them. All timings in these documents come from a
4-core laptop; measure again on the production CPUs.

**Network**

- The classifiers reach `qdrant` on 6333 and 6334 (gRPC is the default;
  `QDRANT_GRPC=false` uses REST only), S3 (`gc-seaweedfs` on 8333) and
  `llm-reranker` on 8080.
- `cron-manager` reaches `qdrant` on 6333, S3 Ferry, Resql, Ruuter, and both
  classifiers through the model-server URLs in `constants.ini`.
- Ruuter reaches the classifiers through the URLs in `constants.ini`.

**Internet access**

- **Image builds:** the `embedding-classifier` build downloads Python packages
  and the e5 weights from Hugging Face; the `llm-reranker` build downloads the
  llama.cpp server image from `ghcr.io` and the pinned Gemma GGUF from Hugging
  Face (checked by SHA-256). The running containers download nothing
  (`HF_HUB_OFFLINE=1`).
- **The first index build in `cron-manager`:** `uv sync --frozen` installs the
  builder's packages into `/app/embedding_venv`, and the builder downloads the e5
  weights into `/app/embedding_models`. Both are volumes, so this happens once.
  Without internet access, fill those volumes in advance.
- The `cron-manager` image must have `uv` (dev has 0.12.5).

## Configuration

### Classifier services (environment)

| Variable | Production | Testing | Notes |
| --- | --- | --- | --- |
| `INDEX_ENV` | `production` | `testing` | Names the file of loaded models, `models/{INDEX_ENV}/_loaded.json` in S3 |
| `QDRANT_URL` | `http://qdrant:6333` | same | |
| `QDRANT_API_KEY` | empty unless Qdrant has one | same | |
| `TORCH_THREADS` | 4 | 4 | Match the CPU limit |
| S3 settings | from `config.env` | same | `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_DATA_BUCKET_NAME`, `S3_DATA_BUCKET_PATH` |
| `SECOND_OPINION_MODE` | `off`, `shadow` or `on` | same | Start with `shadow`; see the rollout below |
| `SECOND_OPINION_URL` | `http://llm-reranker:8080` | same | |
| `SECOND_OPINION_SLOT` | `0` | `1` | Each service keeps its catalogue in its own Gemma slot |
| `SECOND_OPINION_TIMEOUT_MS` | 5000 | 5000 | 4000 keeps the whole request under about 5 s |
| `SECOND_OPINION_TRIGGERS` | `ood_band` | same | `clarify,ood_band` only if the classifier layer is turned off |
| `SECOND_OPINION_MIN_PROBABILITY` | 0.9 | same | Lower rescues more questions and lets more off-topic messages through |
| `SECOND_OPINION_WEIGHT` | 0.25 | same | |

Also mounted, as for the other services: `constants.ini` (read-only) and
`grafana-configs/loki_logger.py`.

### `llm-reranker`

The image sets everything (`LLAMA_ARG_CTX_SIZE=12288`, `LLAMA_ARG_N_PARALLEL=2`,
model baked in). Set `LLAMA_ARG_THREADS` to its CPU limit.

### `cron-manager` (additions)

- **Volumes:**
  - `./src/embedding-classifier` → `/app/src/embedding-classifier`
  - `embedding_venv` → `/app/embedding_venv`
  - `embedding_models` → `/app/embedding_models`
  - `embedding_cache` → `/app/embedding_cache`
- **Environment:** `QDRANT_URL=http://qdrant:6333`, `QDRANT_API_KEY`,
  `EMBEDDING_CACHE_DIR=/app/embedding_cache`.
- **Retention (optional):** `KEEP_RECENT` (default 3) and `KEEP_DAYS` (default 7).

### Builder settings (files in the repo)

| File | Setting | Value shipped | Meaning |
| --- | --- | --- | --- |
| `builder/scoring.json` | `classifier_layer` | `true` | Builds include the classifier layer. A classifier older than this code refuses such builds, so deploy the new classifier image before the first build |
| `builder/quality_gate.json` | `mode` | `enforce` | A GUI build that fails a check is marked failed with its results and isn't deployed; `report` deploys it anyway, like the old trainer |
| `builder/refresh.json` | `enabled`, `environments`, `gate_mode`, `keep_versions` | off (`false`) for now, production + testing, `enforce`, 3 | The automatic refresh; its CronManager job is also `trigger: off` |

## Changes to existing parts

| Part | Change | Needs |
| --- | --- | --- |
| Liquibase | `global-classifier-script-v27-embedding-classifier-base-model.sql`: adds `multilingual-e5-large-instruct` to the `base_models` enum and the GUI's model list | Run the migration |
| Ruuter (private) | `datamodels/create.yml`, `major.yml`, `minor.yml` accept the e5 key; for an e5 model they save the new version undeployed and don't take the production model off (the index builder switches after the build passes and loads). Other base models are unchanged | Restart if it doesn't pick up DSL changes |
| Resql | New `create-refresh-data-model-version.sql`, `insert-refresh-training-job.sql`, `switch-data-model.sql`, `get-group-models-on-dataset.sql` and `update-data-model-environment.sql` (used only by the index builder, the refresh and the rollback tool) | Restart Resql; it reads its queries at start |
| CronManager | New jobs `embedding_index_refresh.yml` (`trigger: off` for now; every 5 minutes when on) and `embedding_index_retention.yml` (daily at 03:00); `train_script_starter.sh` and `deployment_script_starter.sh` route e5 models to the new builder and deploy script, all other models as before | Restart CronManager |
| Scripts | `builder/refresh.sh` and `builder/retention.sh` must be executable | Committed with the executable bit |
| `constants.ini` | `GLOBAL_CLASSIFIER_TESTING_ENV_MODEL_SERVER` and `GLOBAL_CLASSIFIER_PRODUCTION_ENV_MODEL_SERVER` point at the new services | Only at the cutover steps below; not in the release |

## Rollout

The order matters:

- `classify.yml` reads the production model id from the database and sends it
  to whichever server `constants.ini` names, so the id and the server change
  together.
- The builder, its deploy script and the automatic refresh also load models on
  the server `constants.ini` names for the model's environment. An e5 model in an
  environment works only once that environment's URL points at the new service.

Rehearse the whole sequence in a test environment first.

1. **Release** the code, images and containers, and run the migration. Nothing
   changes for users: `constants.ini` still points at Triton, and old base models
   train as before.
2. **Until step 5, create no data model with environment `production`.** Creating
   one moves production to it (an e5 one once it is built), which would point
   classification at a model id Triton doesn't have.
3. **Point only `GLOBAL_CLASSIFIER_TESTING_ENV_MODEL_SERVER`** at
   `http://embedding-classifier-testing:8000`. This affects only the GUI Test
   Model page.
4. **Create a data model** with base model `multilingual-e5-large-instruct` and
   environment `testing`. Check it on the Test Model page and its
   `quality_report.json`. Then also load it on the production classifier:
   `POST /v2/repository/models/{id}-classifier-ensemble/load` on
   `embedding-classifier-production`. Users still go to Triton.
5. **At a quiet time, in one go:**
   - in the database, set the new model's `deployment_env` to `production` and
     the current production model's to `undeployed`;
   - point `GLOBAL_CLASSIFIER_PRODUCTION_ENV_MODEL_SERVER` at
     `http://embedding-classifier-production:8000`;
   - restart Ruuter if it doesn't pick up `constants.ini` changes on its own.

   Classification fails for a few seconds between the first two changes.
6. **Watch for a day:** the decision mix and latency in the classifier's logs
   (see [OPERATIONS.md](OPERATIONS.md)).
7. **Second opinion:** run `SECOND_OPINION_MODE=shadow` for a few days (no added
   wait; it logs what it would have done), check the timings and outcomes, then
   switch to `on`.

**Rollback:** reverse the two changes of step 5: put the old model's row back to
`production` and the production URL back to Triton. Triton still has the old
model loaded unless it was restarted; if it was, deploy that model again through
the old orchestrator. Keep Triton until the new classifier has run long enough.

## Checks after deployment

| Check | How | Expect |
| --- | --- | --- |
| Classifiers alive | `GET /v2/health/live` on each | `{"live": true}` |
| Classifiers ready | `GET /v2/health/ready` | `{"ready": true, "models": [...]}`; 503 while starting or when Qdrant is unreachable |
| Gemma ready | `GET /health` on `llm-reranker` | 200 |
| Catalogue loaded | classifier log line `second_opinion warm-up ms=... prompt_tokens=... slot=...` | Within a few minutes of a model loading, when the mode isn't `off` |
| A build works | Create an e5 data model in testing | Undeployed while it builds; progress reaches "Model Trained And Deployed" and it shows in testing; `models/indexes/{id}/quality_report.json` in S3 |
| A bad dataset is blocked | Create an e5 data model on a dataset version that fails the gate | Training Failed and undeployed; View Results shows the failed check; the production model is unchanged |
| Classification | Test Model page, then `chats/classify` after cutover | Same response shape as before |
| Automatic refresh (once turned on) | After the next dataset version reaches `Generation_Success` | Within a few minutes, a new version of the model (the group's next major version, on the new dataset version) serves in the old one's environment; the old version is undeployed, and the new one is listed under the dataset version on the Datasets page |

## Open decisions before production

These belong to the product lead, not to the deployment:

- how the 90% accuracy target is measured, and the data plan (about 200
  questions per agency that name their topic);
- whether the second opinion may let a few off-topic messages reach an agency
  (4 of 48 in tests at the defaults) in exchange for about +1 point of top-1;
- the expected peak traffic, for a load test: Gemma answers one message at a
  time, and extra unsure messages fall back to e5;
- whether 5 s is the limit for Gemma alone or for the whole request;
- whether to turn on the automatic refresh (shipped off), which adds a new
  version of each e5 model for every new dataset version and switches to it
  when it passes the gate.

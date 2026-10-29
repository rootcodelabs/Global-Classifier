# Dataset Generator Module Integration Tests

Integration tests covering the dataset-generation slice that **this repo owns**:
the Ruuter.public DSL, the Resql SQL endpoints, the CronManager shell scripts,
and `src/s3_dataset_processor`. Everything in that list runs for real against
live containers - no mocks, no monkeypatching.

Run by `.github/workflows/dataset-generator-integration.yml` on pull requests
into `feature/ckb-data-syncing`, `v1.0.0`, `v2.0.0` or `main` that touch the
dataset-generation paths, and on demand via `workflow_dispatch`.

## What is real vs. stubbed

| Component | Status | Notes |
|---|---|---|
| Ruuter.public | Real | `ghcr.io/buerokratt/ruuter:v2.2.8`, mounts `DSL/Ruuter.public` |
| Resql | Real | `ghcr.io/buerokratt/resql:v1.3.6`, mounts `DSL/Resql` |
| Postgres + Liquibase | Real | Full `DSL/Liquibase` migration runs per session |
| CronManager | Real | Runs the actual `dataset_pipeline_s3.sh` unmodified |
| `s3_dataset_processor` | Real | `download_source_dataset.py` executes for real |
| SeaweedFS (S3) | Real | Hosts the fixture agency-data zip, serves a presigned URL |
| Data Mapper | **Stubbed** | `test_doubles/` - only supplies a random hex string |
| notifications-node | **Stubbed** | `test_doubles/` - avoids needing OpenSearch |
| Dataset-Generator service | **Stubbed** | `test_doubles/` - avoids needing LLM keys/cost |

The three stubs are deliberate: they are external to this repo, and two of them
(notifications, generator) would drag in OpenSearch and a paid LLM provider for
no additional coverage of code this repo is responsible for.

## Layout

```
tests/integration_tests/
  conftest.py                           Stack lifecycle + pytest fixtures
  constants.test.ini                    Service URLs, points at the stubs
  test_dataset_generator_pipeline.py    The tests
  seaweedfs/s3_config.json              S3 credentials for the object store
  test_doubles/                         Flask stub for the 3 external services
    app.py
    Dockerfile
    requirements.txt
```

The compose file lives at the repo root: `docker-compose-test.yml`.

## Running locally

```bash
uv sync --frozen --group dev
chmod +x DSL/CronManager/script/*.sh
docker compose -f docker-compose-test.yml build      # builds the stub image only
uv run pytest tests/integration_tests/ -v
```

Takes roughly 30 seconds once images are present. The `gc_stack` fixture is
session-scoped, so the stack comes up once and is torn down automatically -
you do not need to start or stop anything yourself.

To inspect a failure, bring the stack up by hand and leave it running:

```bash
docker compose -f docker-compose-test.yml up -d
docker compose -f docker-compose-test.yml logs cron-manager -f
```

Note that a manual `up` does **not** run the Liquibase migration (the fixture
does that). Without it, Resql inserts fail on the missing
`dataset_progress_sessions` table. Run the migration step from
`conftest.py::_run_database_migration` if you need a working manual stack.

## What the tests assert

**`TestProgressSessionLifecycle`** - the Ruuter DSL and Resql SQL for progress
sessions. Creates and updates a session over HTTP, then reads the row straight
out of Postgres to confirm it actually persisted with the right status and
percentage.

**`TestDatasetPipelineTrigger`** - the full pipeline script, end to end:

1. Uploads a fixture zip to the S3 store and presigns it.
2. Triggers the real CronManager job over HTTP
   (`POST /execute/dataset_pipeline_scheduler/dataset_pipeline_schedule`).
3. `dataset_pipeline_s3.sh` runs unmodified: downloads over S3, extracts the
   zip, builds the generator payload, and POSTs it.
4. Asserts the stub received a well-formed payload with the right agency fields.
5. Asserts the progress session advanced to a real downstream status.

## Prerequisites

None beyond Docker and `uv` - every image is pullable. The cron-manager service
is pinned to `ghcr.io/buerokratt/cronmanager:python-1.2.0` by digest, the only
published tag that ships a Python venv and `uv`; see the comment in
`docker-compose-test.yml` before changing it.

## Running against the real generator instead

Swapping the stub for the real `synthesisai/dataset-generator` image is
feasible, and worth doing as a separate non-blocking workflow rather than a PR
gate. Measured characteristics:

- The image is ~9.87GB unpacked (~3.1GB pulled). A GitHub-hosted runner needs a
  disk-reclaim step to fit it.
- Cold start is ~100s, because the `paraphrase-multilingual-mpnet-base-v2`
  embedding model is **not** baked into the image and downloads at runtime.
- Redis is a hard dependency; `/generate-bulk` returns 503 without it, and the
  hostname must resolve as `redis` to match `config.yaml`.
- Both `config/` and `user_configs/` must be mounted. With only `config/` you
  get `Found 0 dataset structures` and generation fails.
- With Azure OpenAI as the provider, Ollama and its GPU requirement drop away
  entirely.

The reason to keep it out of the PR gate is determinism, not time: generation is
gated on quality thresholds (`topic_coverage_min`, `overall_min`, and friends in
`config.yaml`) with up to 3 regeneration attempts, so a run can fail on LLM
variance rather than on a code change. If you do wire it up, assert only on
structure - payload accepted, callback fired, CSV columns correct - and never on
generated content.

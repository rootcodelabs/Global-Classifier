# Global Classifier AI Coding Instructions

## Code Style Requirements

**CRITICAL: Never use emojis in any generated code, comments, log messages, or documentation. Use plain text only.**

## Architecture Overview

Global Classifier is a machine learning platform built on the **BYK Stack** - a microservices architecture with specialized DSL-based components:

- **Ruuter**: API gateway handling REST endpoints via YAML DSL configurations (`DSL/Ruuter.public/`, `DSL/Ruuter.private/`)
- **Resql**: Database abstraction layer using SQL files as endpoints (`DSL/Resql/global-classifier/`)
- **Data Mapper**: Template engine for dynamic content generation (`DSL/DMapper/`)
- **TIM**: Authentication and authorization service
- **CronManager**: Scheduled task execution

## Key Development Patterns

### DSL-First API Development
APIs are defined declaratively in YAML files, not traditional controllers:
```yaml
# DSL/Ruuter.private/global-classifier/POST/inference/deploy.yml
declaration:
  call: declare
  method: post
  accepts: json
  allowlist:
    body:
      - field: modelId
        type: string
```

### Database Operations via Resql
Database interactions use `.sql` files as endpoints, not ORM models:
```sql
-- DSL/Resql/global-classifier/POST/insert-data-models.sql
INSERT INTO public.data_models (model_name, deployment_env, base_models)
VALUES (:modelName, :deploymentEnv, :baseModels::jsonb)
```

### Service Configuration in constants.ini
All service URLs are centralized in `constants.ini` using `[#SERVICE_NAME]` placeholder syntax:
```ini
GLOBAL_CLASSIFIER_RUUTER_PRIVATE=http://ruuter-private:8088/global-classifier
GLOBAL_CLASSIFIER_RESQL=http://resql:8082/global-classifier
```

### CronManager Scripts
Job definitions are in `DSL/CronManager/DSL/`, and the shell scripts they run are in `DSL/CronManager/script/`. Every script starts with `source /app/scripts/load_constants.sh`, which exports the values in `constants.ini` as shell variables:
```bash
source /app/scripts/load_constants.sh
curl -s -X POST "${GLOBAL_CLASSIFIER_RUUTER_PUBLIC}/agencies/data/start-generation"
```
Python scripts under `src/s3_dataset_processor/` read the same file through `constants.py`. CronManager passes a job only the variables in its `allowedEnvs`, and not `PATH`, so scripts that run Python activate `/app/python_virtual_env` by absolute path.

## Development Workflows

### Environment Setup
```bash
# Use uv package manager (mandatory)
uv venv && uv sync
source .venv/bin/activate

# Build required BYK stack images first
docker build -t ruuter . # in cloned Ruuter repo
docker build -t resql . # in cloned Resql repo
```

### Testing Requirements
- **Linting**: All code must pass `ruff check .` and `ruff format .`
- **Unit tests**: `uv run pytest src/tests/ -v`
- **Integration tests**: `uv run pytest tests/integration_tests/ -v` (needs Docker, see `tests/integration_tests/README.md`)
- **Commit messages**: `type(ticket): description`, for example `fix(0): ...`, enforced by `.husky/commit-msg`

### Branch Strategy
1. **wip** → **testing** → **dev** (three-tier workflow)
2. All PRs target `wip` branch first
3. Automated validation in `testing` before promoting to `dev`

## Component Structure

### Python Services (`src/`)
- `model-training/`: ML model training scripts
- `inference/`: Model serving (prod/testing environments)  
- `classifier-service/`: Node.js mock service for chat classification
- `dataset_file_handler/`: Data processing utilities
- `s3_dataset_processor/`: Scripts CronManager runs to download agency data and build dataset versions

### Frontend (`GUI/`)
- React + TypeScript with Vite
- Radix UI components and TanStack Query
- Multi-language support via `translations/`

### Experiments (`experiments/`)
- `base_model_training/`: BERT/RoBERTa/XLM model experiments
- `ood_detection/`: Out-of-distribution detection research

## Critical Integration Points

### Authentication Flow
Routes use `.guard` files for auth checks. Private routes require cookie-based authentication validated through TIM service.

### Agency Data Sync
Agencies and their CKB data come from CentOps. GC never calls CKB directly, and the old mock tables (`mock_centops`, `mock_ckb`) are gone.
1. The `centops_poll` job (hourly) calls `GET /agencies/data/poll-centops`, which saves agencies to `integrated_agencies` and new or changed data to `agency_data_requests`
2. The `agency_data_sync` job (every 5 minutes) calls `POST /agencies/data/start-generation`, which claims all `PENDING` requests into one dataset generation run (one run at a time)
3. The Dataset Generator calls back on `POST /data/callback`, and `POST /agencies/data/generation` records the outcome
4. Agencies with `part_of_network = FALSE` are dropped from classification results and from the next dataset version

Full design: `docs/architecture/data-pipeline-architecture.md`.

### Model Deployment Pipeline
1. Create model metadata → Resql `insert-data-models.sql`
2. Update dataset connections → `update-datasets-connected-models.sql`  
3. Initiate training → Call `/datamodels/train` endpoint
4. Environment progression: undeployed → testing → production

### Configuration Management
- Docker services defined in multiple compose files (dev, inference-cpu, inference-gpu)
- Environment-specific configurations in `config.env` and `sidecar.env`
- Service discovery via DNS names in docker network `bykstack`

## Common Anti-Patterns to Avoid

- **Don't** create traditional REST controllers - use Ruuter YAML DSL
- **Don't** write raw SQL in application code - use Resql `.sql` files
- **Don't** hardcode service URLs - reference `constants.ini` placeholders
- **Don't** fetch agency data from CKB directly - it arrives through the CentOps poll
- **Don't** bypass authentication guards on private routes
- **Don't** use pip/conda - project requires `uv` package manager

## Quick Reference

### Adding New API Endpoint
1. Create YAML in `DSL/Ruuter.{public|private}/global-classifier/{METHOD}/`
2. Add SQL queries in `DSL/Resql/global-classifier/{METHOD}/`
3. Update service constants if calling external services
4. Add authentication guard if private endpoint

### Running Services Locally
```bash
docker-compose up -d  # Full stack
docker-compose -f docker-compose-dev.yml up  # Development mode
```

### Model Training/Inference
- Training: Triggered via `/datamodels/train` POST endpoint
- Inference: Environment-specific deployments in `src/inference/{prod|testing}/`
- Models support: BERT, RoBERTa, XLM base architectures

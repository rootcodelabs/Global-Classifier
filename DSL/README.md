# DSL

Declarative configuration for the BYK stack services that make up the Global Classifier backend. Service URLs are never hardcoded: Ruuter and Resql files use `[#NAME]` placeholders, and CronManager scripts use shell variables. Both are filled in from `constants.ini` at the repo root.

| Folder | Service | Contents |
|---|---|---|
| `Ruuter.public/global-classifier/` | Ruuter public (port 8086) | Endpoints called by other services and CronManager: classification, the CentOps poll, dataset generation and its callbacks. |
| `Ruuter.private/global-classifier/` | Ruuter private (port 8088) | Endpoints used by the GUI, behind TIM authentication guards. |
| `Resql/global-classifier/` | Resql | One SQL file per database query endpoint. |
| `DMapper/global-classifier/` | Data Mapper | Handlebars templates (`hbs/`) and the JavaScript helpers they call (`lib/helpers.js`). |
| `Liquibase/` | Liquibase | Database migrations. `master.yml` lists the changelogs in the order they run. |
| `CronManager/` | CronManager | Job definitions (`DSL/`) and the shell scripts they run (`script/`). |
| `DatasetGenerator/` | Dataset Generator | Config, templates and output folder mounted into the generator container. |
| `OpenSearch/` | OpenSearch | Index mappings for the dataset and model progress sessions. |

## CronManager jobs

Scheduled jobs use Quartz cron expressions, which start with a seconds field. On-demand jobs are started over HTTP with `POST [#GLOBAL_CLASSIFIER_CRON_MANAGER]/execute/<definition file name>/<job name>`, and their inputs must be listed in `allowedEnvs`.

| Job | Definition | Schedule | Script | What it does |
|---|---|---|---|---|
| `centops_poll` | `centops_poll.yml` | Hourly, on the hour | `centops_poll.sh` | Polls CentOps for the agency list and new agency data. |
| `agency_data_sync` | `data_sync.yml` | Every 5 minutes | `agency_data_sync.sh` | Starts a dataset generation run if any agency data is pending. |
| `dataset_pipeline_schedule` | `dataset_pipeline_scheduler.yml` | On demand | `dataset_pipeline_s3.sh` | Downloads agency data and calls the Dataset Generator. |
| `callback_format` | `callback_formatter.yml` | On demand | `callback_format.sh` | Processes the generator's callback and builds the new dataset version. |
| `dataset_remove_agencies` | `dataset_remove_agencies.yml` | On demand | `dataset_remove_agencies.sh` | Builds a dataset version without the agencies that left the network. |
| `model_trainer` | `data_model.yml` | Every minute | `train_script_starter.sh` | Starts the next queued model training job if none is running. |
| `delete_completed_sessions` | `data_model_progress_session.yml` | Daily at midnight | `delete_completed_data_model_progress_sessions.sh` | Deletes completed model training progress sessions. |
| `deploy_model` | `deploy.yml` | On demand | `deployment_script_starter.sh` | Runs the model deployment orchestrator. |

The first five jobs make up the agency data sync. See [Agency Data Sync and Dataset Pipeline](../docs/architecture/data-pipeline-architecture.md).

### Writing a CronManager script

- Start the script with `source /app/scripts/load_constants.sh`. It exports every value in `constants.ini`, which is mounted at `/app/constants.ini`, so the script calls the same URLs as Ruuter.
- CronManager passes a job only the environment variables listed in its `allowedEnvs`, and `PATH` is not one of them. Scripts that run Python activate `/app/python_virtual_env` by absolute path first.

# Documentation

## Architecture

| Document | Covers |
|---|---|
| [Agency Data Sync and Dataset Pipeline](architecture/data-pipeline-architecture.md) | How GC gets agency data from CentOps, runs dataset generation, builds dataset versions, and handles agencies that leave or rejoin the network. |
| [First-Time Agency Dataset Import Flow](architecture/first-time-agency-dataset-import-flow.md) | The path of a new agency from CentOps to its first dataset version. |

Diagrams in these documents use Mermaid, which GitHub renders.

## Drawio diagrams

| File | Covers |
|---|---|
| [global-classifier-dataset-pipeline-architecture.drawio](architecture/global-classifier-dataset-pipeline-architecture.drawio) | Original dataset pipeline design. |
| [global-classifier-dataset-pipeline-architecture -v2.drawio](architecture/global-classifier-dataset-pipeline-architecture%20-v2.drawio) | Second iteration of the dataset pipeline design, including an early CentOps polling flow. |
| [gc_model_training_module.drawio](gc_model_training_module.drawio) | Model training module design. |

The dataset pipeline diagrams predate the CentOps data sync. They show, for example, a 15-minute cron job calling a `/centops/api/v1/agencies/new` endpoint. Where they differ from the markdown documents above, the markdown documents describe the system as built.

## Elsewhere in the repo

- [DSL/README.md](../DSL/README.md): the DSL folders and CronManager jobs.
- [tests/integration_tests/README.md](../tests/integration_tests/README.md): dataset generator integration tests.
- [experiments/base_model_training/README.md](../experiments/base_model_training/README.md) and [experiments/ood_detection/README.md](../experiments/ood_detection/README.md): model and out-of-distribution detection experiments.

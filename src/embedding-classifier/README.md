# Embedding classifier

Training-free agency classifier that replaces the GPU-trained model. An
off-the-shelf multilingual embedding model (`intfloat/multilingual-e5-large-instruct`
by default) embeds each agency's example questions; the vectors live in Qdrant.
A message is scored per agency by meaning (mean of its 5 closest stored texts)
and by character n-gram keywords, the two are fused (with a small keyword
classifier trained on the same rows, on by default), and a confidence gate
routes it, asks the citizen to clarify, or flags it as off-topic. Everything
runs on CPU; adding or changing an agency means rebuilding the index, not
training.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): what changed from the trained model, how it works, the
  choices behind it and the measured results.
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md): what to deploy, requirements, configuration, rollout and
  rollback, for the team that deploys it.
- [docs/OPERATIONS.md](docs/OPERATIONS.md): the automatic jobs, common tasks, testing a dataset by hand,
  logs and troubleshooting.

## Layout

| Path | What it is |
| --- | --- |
| `embedding_classifier/` | Core library, no web framework and no S3: encoder, content cleaning, keyword vectors, the Qdrant and in-memory index stores, scoring, gate, calibration, output format, build files, evaluation measures |
| `embedding_classifier/embedding_models.json` | The model keys the builder accepts, each with its Hugging Face id and pinned revision |
| `service/` | The classifier service: FastAPI app answering the Triton v2 calls the DSL makes, and the index registry |
| `builder/` | The index build job (run by `train_script_starter.sh`), deploy script (run by `deployment_script_starter.sh`), daily retention job, restore script; `quality_gate.json` holds the gate's thresholds and mode, `scoring.json` turns the classifier layer on |
| `embedding_classifier/classifier_layer.py` | The optional classifier layer (see below) |
| `embedding_classifier/dataset_check.py`, `tools/dataset_check.py` | The dataset check (see below) |
| `tools/evaluate_kb.py` | Evaluation on the agency knowledge base (kept outside the repo, passed by path) |
| `tools/second_opinion_benchmark.py` | Decides whether to turn the second opinion on (see below) |
| `tools/build_local_index.py` | Builds an index from a local `aggregated_dataset.csv` for development |
| `tests/` | Unit, contract and builder tests with a fake encoder; no model download |
| `Dockerfile` | The service image: CPU-only torch, the pinned e5 weights baked in, `HF_HUB_OFFLINE=1` |
| `llm-reranker/Dockerfile` | The second-opinion model server: llama.cpp's `llama-server` with a pinned Gemma 4 E4B GGUF baked in |

## How it runs

- **Service:** `embedding-classifier-production` and `embedding-classifier-testing` in `docker-compose-dev.yml`, one image, `INDEX_ENV` naming which loaded-set file (`models/{INDEX_ENV}/_loaded.json` in S3) each keeps. They load `{id}-classifier-ensemble` from `models/indexes/{id}/` in S3 and the `gc_index_{id}` collection in Qdrant. `LOCAL_MODELS_DIR` replaces S3 with a local folder of the same layout.
- **Build:** for a data model whose base model is an embedding key, `train_script_starter.sh` syncs this project into `/app/embedding_venv` and runs `python -m builder.cli` with the trainer's arguments. The GUI saves such a model undeployed and leaves the model serving its environment alone. The gate runs in `enforce` mode (`builder/quality_gate.json`): a build under its limits is marked `training_failed` with its results and keeps no collection; one that passes is loaded and then takes its environment, in production in place of the model serving there (`switch-data-model.sql`), which is unloaded a few seconds later. Other base models train as before.
- **Deploy:** when `models/indexes/{id}/manifest.json` exists, `deployment_script_starter.sh` runs `python -m builder.deploy` instead of the Triton orchestrator.
- **Automatic refresh (living model, off for now):** shipped with `trigger: off` in `DSL/CronManager/DSL/embedding_index_refresh.yml` and `"enabled": false` in `builder/refresh.json` until the team decides; turning it on takes both (see `docs/OPERATIONS.md`). When on, every 5 minutes `builder/refresh.sh` looks for a newer dataset version with `Generation_Success` and gives each model group with an e5 model in production or testing a new version built from it, as an admin's major update in the GUI would: a new data model row (the group's next major version, on the new dataset version, undeployed) and a training job that makes GUI trainings wait meanwhile. The gate runs in `enforce` mode. If the build passes and loads, one query (`switch-data-model.sql`) puts the new version in the old one's environment and the old one to undeployed, and the old one is unloaded a few seconds later; if it fails, the new version stays as a failed row and the old one keeps serving. A group that already has a version on the dataset version isn't refreshed from it again. `python -m builder.rollback --model-id {earlier} --replacing {serving}` switches back. Other settings are in `builder/refresh.json`.
- **Retention and restore:** `DSL/CronManager/DSL/embedding_index_retention.yml` runs `builder/retention.sh` daily (`KEEP_RECENT`, `KEEP_DAYS`, and `keep_versions` per model); `python -m builder.restore --model-id {id}` recreates a collection from its snapshot.
- **Classifier layer (on):** with `"classifier_layer": true` in `builder/scoring.json` (set to `false` to build without it), each build also trains a logistic regression on the index's own keyword vectors and adds its log-probabilities to the neighbour scores, with weights chosen on the calibration split (a weight of 0 for the regression is today's ranking). It is saved as `classifier_layer.npz` next to the manifest (format version 2, so an older service refuses the build instead of serving it without the layer), and the service applies it after the Qdrant search. On the developer dataset it raised top-1 from 75.7% to 77.8% on average over 5 splits; on the builder's own split, the share routed at 90% accuracy went from 68.6% to 78.2%. Builds take about 40 s longer; serving is unchanged in speed. `classifier_c` is the regression's inverse regularisation strength.
- **Second opinion (off by default):** for messages flagged off-topic within `SECOND_OPINION_OOD_BAND` of the cutoff (and for `clarify` messages too when `SECOND_OPINION_TRIGGERS` includes `clarify`), the service asks the `llm-reranker` container (Gemma 4 E4B on CPU, llama.cpp) to choose among e5's top 3 or none. The prompt (version 2) opens with the build's catalogue, every agency with its 3 most typical questions, which the service builds when a model loads and sends once so the server caches it; each call then adds only the message and the three options by number, about 50 tokens. The answer is forced to one letter. Its letter probabilities are combined with e5's confidences (`SECOND_OPINION_WEIGHT`), and a borderline off-topic message is rescued only when the model is at least `SECOND_OPINION_MIN_PROBABILITY` sure of one of the three. Each service keeps its catalogue in its own server slot (`SECOND_OPINION_SLOT`: production 0, testing 1). `SECOND_OPINION_MODE` is `off` (no call, output unchanged), `shadow` (asks in the background and only logs) or `on` (applies the answer within `SECOND_OPINION_TIMEOUT_MS`, 5 s). Other settings: `SECOND_OPINION_URL`, `SECOND_OPINION_MAX_CONCURRENT`. Measured results are under "Second opinion results" below.

## Setup

```bash
cd src/embedding-classifier
uv sync          # Python 3.12, CPU-only torch, qdrant-client 1.19.1
```

Local Qdrant, the version this package is pinned to:

```bash
docker run -d --name qdrant -p 127.0.0.1:6333:6333 -p 127.0.0.1:6334:6334 qdrant/qdrant:v1.19.2
```

## Tests

```bash
uv run pytest                                   # Qdrant through qdrant-client's local mode
QDRANT_URL=http://127.0.0.1:6333 uv run pytest  # also against a running server
```

## Knowledge base evaluation

```bash
uv run python -m tools.evaluate_kb \
    --kb <knowledge base folder> \
    --off-topic <off-topic messages> \
    --off-topic ../../experiments/ood_detection/data/ood_test.csv \
    --store qdrant --qdrant-grpc --parity --out <results folder>
```

`--model` takes a key from `embedding_models.json`. Embeddings are cached in
`<results folder>/cache` (or `--cache`), so a second run embeds nothing.
`--kb` is a knowledge-base folder (`faq.csv` with agencies' real questions and
answers, plus agency content). `--off-topic` takes a CSV of conversations, a
text file with one message per line, or a Python file with an `OFF_TOPIC` list.
Results go to `RESULTS.md` and `results.json` in the results folder; keep
them out of the repo, like the knowledge base. With
`--second-opinion-url http://127.0.0.1:8012`, stores B and D are also reported
with the second opinion applied.

## Second-opinion benchmark

With a model server running (`docker compose -f docker-compose-dev.yml up -d llm-reranker`,
host port 8012):

```bash
uv run python -m tools.second_opinion_benchmark \
    --kb <knowledge base folder> \
    --off-topic <off-topic messages> \
    --off-topic ../../experiments/ood_detection/data/ood_test.csv \
    --extra <multilingual questions>.csv \
    --model gemma-4-e4b --url http://127.0.0.1:8012 --out <results folder>
```

`--extra` CSVs have the columns `text`, `agency_id` (a knowledge-base agency,
or empty for off-topic) and `language`. The prompts are written once; run the
command again with another `--model` and `--url` to compare models on the same
messages, and `--limit N` for a quick run. `SUMMARY.md` gives fixed, broken,
the net top-1 gain, off-topic messages routed, the answer mix, timings and a
go or no-go per model.

## Second opinion results

Prompt version 2 on a generated development dataset (37 agencies, 3,934 questions), the builder's
scoring and gate, a laptop with
4 CPU cores. Test questions: 3 random splits with the classifier layer on, 1,185 in all. Off-topic: 48
messages (a hand-written list and `experiments/ood_detection/data/ood_test.csv`). Top-1 here is the first entry of the output, so a
question flagged off-topic counts as wrong; that is why it is below the 77.8% ranking figure.

| Settings | Overall top-1 | Off-topic messages that reach an agency |
| --- | --- | --- |
| Mode off | 75.0% | 12 of 48 |
| `ood_band`, min probability 0.9 (the defaults) | +1.0 point (12 questions rescued to the right agency) | 16 of 48 |
| `ood_band`, min probability 0.5 | +1.9 points | 19 of 48 |
| `clarify,ood_band`, weight 0.25, min probability 0.5 | +1.6 points (clarify: 7 fixed, 9 broken) | 19 of 48 |

- **With the classifier layer off,** asking about `clarify` messages helps (weight 0.25: 17 fixed, 8 broken
  over 2 splits), so `clarify,ood_band` suits that setup.
- **Speed:** a call takes 3.0-3.7 s typical and 4.5-5.8 s for the slowest 5%; 90-97% answer within the
  5 s limit. The catalogue (about 2,400 tokens) takes about 100 s to read after a model loads; until then
  e5's answer stands.
- **Prompt version 1** (3 examples per candidate in every call) took 10-13 s, and the benchmark below
  still measures that version.

## Dataset check

Finds the questions the classifier can't learn from as written, for people
who know the agencies to review:

```bash
uv run python -m tools.dataset_check --csv aggregated_dataset.csv --out <folder>
```

Every question is scored against the rest of the dataset (5-fold
cross-validation with the classifier's own scoring), and each one it gets
wrong is given a likely cause: `no_clue` (nothing in it points to an agency:
rewrite it to name its topic, or remove it), `shared_topic` (the labelled
agency was 2nd or 3rd: decide which agency owns the topic), `check_label`
(the labelled agency ranked 6th or lower: the label may be wrong) or `other`.
`dataset_check.md` has the counts, a table per agency (with the ones under
100 questions marked), the agency pairs that share topics with examples, and
the questions to check; `dataset_check.csv` lists every mistake. The causes
come from simple rules, so they are candidates, not verdicts. Embeddings are
cached in `<folder>/cache` (or `--cache`).

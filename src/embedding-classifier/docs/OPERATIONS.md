# Running the embedding classifier

Day-to-day tasks, testing and troubleshooting. Most of it runs on its own:
people step in to roll back, restore, review a dataset or test one by hand.
What the parts are is in [ARCHITECTURE.md](ARCHITECTURE.md); how to deploy them
is in [DEPLOYMENT.md](DEPLOYMENT.md).

Commands are for a Linux shell. In Git Bash on Windows, put `MSYS_NO_PATHCONV=1`
in front of any `docker exec` whose arguments start with `/`, or Git Bash
rewrites the path.

## What runs on its own

| Job | When | What it does |
| --- | --- | --- |
| Automatic refresh (`builder/refresh.sh`) | **Off for now**, until the team decides: `trigger: off` in CronManager `embedding_index_refresh` and `"enabled": false` in `builder/refresh.json`. When on, every 5 minutes | When a dataset version newer than a model's reaches `Generation_Success`, adds a new version to each model group with an e5 model in production or testing (its production model, or else its newest testing one), as an admin's major update in the GUI would: a new data model row with the group's next major version (V1.0 → V2.0) on the new dataset version, undeployed while it builds, with a training job that makes GUI trainings wait. The quality gate runs in `enforce` mode. If the build passes and loads, the new version takes the old one's environment and becomes the latest, the old one becomes undeployed and is unloaded, and the new one is listed under the dataset version's connected models. If not, the new version stays as a failed row and the old one keeps serving. A group that already has a version on the dataset version isn't refreshed from it again |
| Clean-up (`builder/retention.sh`) | Daily at 03:00 in the container's time zone (`embedding_index_retention`) | Deletes old Qdrant collections and unloads those models from both classifiers. Keeps every model in production or testing, the 3 most recent others (`KEEP_RECENT`), anything built in the last 7 days (`KEEP_DAYS`), and for each kept model the collection it serves plus its `keep_versions` newest others. S3 build files and snapshots are never deleted, so any build can be restored |
| Catalogue warm-up | After a model loads, when `SECOND_OPINION_MODE` isn't `off` | Sends the build's agency catalogue to Gemma, which caches it; re-sent after a timeout or error, at most once a minute |

The dataset pipeline's callback writes `datasets/{id}/aggregated_dataset.csv`
and marks the version `Generation_Success`. While the refresh is off, a new
dataset version reaches users only when an admin creates a data model, or a new
version of one, on it in the GUI.

## Where things are

| What | Where |
| --- | --- |
| A dataset version | S3 `datasets/{id}/aggregated_dataset.csv` |
| A model's current build | S3 `models/indexes/{id}/`: `manifest.json`, `keywords.json`, `quality_report.json`, `collection.snapshot`, `classifier_layer.npz` |
| The models a classifier reloads at start | S3 `models/{production or testing}/_loaded.json` |
| Collections | Qdrant `gc_index_{id}`, one per data model version |
| Builder environment, e5 weights, embedding cache | `cron-manager` volumes `/app/embedding_venv`, `/app/embedding_models`, `/app/embedding_cache` |

Builder commands run in `cron-manager` from `/app/src/embedding-classifier`
with `/app/embedding_venv/bin/python`.

## Common tasks

**Turn the automatic refresh on:** set `"enabled": true` in
`builder/refresh.json` (read on every run), replace `trigger: off` with
`trigger: "0 0/5 * * * ?"` in `DSL/CronManager/DSL/embedding_index_refresh.yml`,
and restart `cron-manager`, which reads its job files at start. Reverse both to
turn it off.

**Run the refresh now** instead of waiting for the schedule. It needs
`"enabled": true`, and it holds a lock, so it can't clash with a scheduled run:

```bash
docker exec cron-manager /app/src/embedding-classifier/builder/refresh.sh
```

**Switch back to the earlier version** after a refresh. The earlier version
goes back to the environment, the newer one becomes undeployed:

```bash
docker exec -w /app/src/embedding-classifier cron-manager \
  /app/embedding_venv/bin/python -m builder.rollback --model-id <earlier id> --replacing <serving id>
```

If the clean-up already deleted the earlier version's collection, it is
restored from its snapshot. Rows, version numbers, results and `latest` stay
as they are, and the refresh doesn't rebuild from that dataset version again,
since the group already has a version on it. The same command switches to a
version the refresh built but couldn't switch to (its log says so). The GUI
can't do this: changing only a model's environment there doesn't reach the
database.

**Try a dataset version again after the gate blocked it:** the refresh skips a
dataset version once the model group has a version on it, failed or not.
Delete the failed version on the Data Models page and the next run tries
again, or publish a fixed dataset version.

**Restore a lost collection** (Qdrant data lost, `/v2/health/ready` fine but
loading fails with "Collection ... is missing"):

```bash
docker exec -w /app/src/embedding-classifier cron-manager \
  /app/embedding_venv/bin/python -m builder.restore --model-id <id>
```

**Read a build's quality** from `models/indexes/{id}/quality_report.json`.
Under `metrics`:

- `top1` and `top3`;
- `routed_share` and `routed_accuracy`: answered without asking to clarify, and
  how many of those were right;
- `routed_at_90_share`;
- `real_wrongly_flagged`: real questions flagged off-topic;
- `decision_mix` and `per_agency`.

`gate.checks` lists each check as passed, failed or skipped, and `warnings` holds
notes such as too few calibration questions.

**Review a dataset** before or after it ships, from a machine with the
repository and `uv`:

```bash
cd src/embedding-classifier
uv run python -m tools.dataset_check --csv aggregated_dataset.csv --out check/
```

`check/dataset_check.md` lists accuracy per agency, agencies under 100
questions, agency pairs that share topics, and the questions to fix.

**Change the second opinion's mode:** set `SECOND_OPINION_MODE` (`off`,
`shadow`, `on`) on both classifier services and recreate the containers. It
takes effect at once; no rebuild is needed.

**Turn the classifier layer off or on:** `classifier_layer` in
`builder/scoring.json`. It applies from the next build.

## Testing a dataset by hand (dev)

To test a CSV that didn't come from the dataset pipeline:

1. Upload it to S3 as `datasets/<next id>/aggregated_dataset.csv`. The name must
   be exactly that. The columns are `data_item`, `agency_name`, `agency_id`.
   Agencies with fewer than 5 questions are left out.
2. Mark it successful, as the pipeline would:

   ```bash
   docker exec users_db psql -U postgres -d global-classifier \
     -c "INSERT INTO dataset_versions (major, minor, generation_status) VALUES (<major>, 0, 'Generation_Success') RETURNING id;"
   ```

   The returned id must match the folder.
3. Create a data model in the GUI with base model
   `multilingual-e5-large-instruct`, that dataset version and environment
   `testing`, and wait for "Model Trained And Deployed", or Training Failed if
   the dataset fails the quality gate. With the refresh on,
   existing models get a new version instead: expect
   `Model <new id> (version <x>, dataset <version>) now serves <environment> in place of model <old id>`,
   or `failed the quality gate` (the old version keeps serving).
4. Read `models/indexes/<id>/quality_report.json`; after a refresh, `<id>` is
   the new version's id.
5. To undo a refresh, switch back as above.

## Testing in the GUI

Log in to the GUI and open Test Model. It loads a model on the testing
classifier, which has no network filter, so every agency in the build can come
back.

## Testing classification directly

```bash
curl -s -X POST http://<classifier>:8000/v2/models/<id>-classifier-ensemble/infer \
  -H "Content-Type: application/json" \
  -d '{"inputs":[{"name":"TEXT","datatype":"BYTES","shape":[1,1],"data":[["Kuidas registreeruda riigieksamile?"]]}]}'
```

`outputs[0]` is what `classify.yml` reads (agencies and confidences).
`outputs[1]` is the decision: route, clarify or off-topic, the margin, the top
similarity, and `second_opinion` when Gemma was asked. In the dev stack the host
ports are 8010 (production), 8011 (testing) and 8012 (Gemma).

Through the public endpoint, `chats/classify` returns only agencies in
`integrated_agencies` with `part_of_network = true`; anything else comes back as
`out_of_distribution`.

## Logs

The classifier services log, per message:

```text
model=1 decision=route margin=0.412 top_similarity=0.987 latency_ms=402
```

and per second opinion:

```text
second_opinion model=1 mode=on trigger=ood_band top3=[...] answer=B probability=0.875 applied=False ms=2844 outcome=ok prompt_version=2
```

plus `second_opinion warm-up ms=... prompt_tokens=... slot=...` after a load.
Message text is never logged.

The refresh logs `Model <old id> (<env>, version <x>, dataset <a>): building
version <y> as model <new id> from dataset <b>`, then `Model <new id> ... now
serves <env> in place of model <old id>`, or `failed the quality gate ...;
model <old id> keeps serving`. Otherwise it logs `Every model is up to date
with dataset <n>`, `its group already has a version on dataset <n> ...; waiting
for a newer dataset version`, `A training is running; refreshing next time`,
or `Automatic refresh is off`. After a crash, the next run logs `An earlier
refresh stopped while building model <id> ...; settling it` and marks that
version and its training job failed.

What to watch:

- **Decision mix:** a jump in clarify or off-topic decisions after a new build
  means the build or the data changed.
- **Latency:** messages Gemma isn't asked about take under a second; those it is
  asked about take up to the limit plus e5's time.
- **Second-opinion outcomes:** mostly `ok`. Many `timeout` means the CPU is too
  slow or the catalogue isn't cached; many `busy` means more unsure messages than
  Gemma can answer one at a time; `error` means `llm-reranker` is down.

## Troubleshooting

| Symptom | Likely cause | What to do |
| --- | --- | --- |
| A new dataset version doesn't reach a model | The automatic refresh is off | Create a data model on the version in the GUI, or turn the refresh on |
| The refresh says `Every model is up to date` after a new upload | The new version isn't marked `Generation_Success`, or it isn't newer than the model's | Check `dataset_versions` |
| The refresh fails to download the dataset | The file isn't named `aggregated_dataset.csv`, or it's in another folder than the version id | Rename or move it |
| `failed the quality gate` | The new build is under the limits in `quality_gate.json` (top-3, real questions flagged off-topic); the checks against the live build are skipped until there is a golden set | Read `gate.checks` in the new version's `quality_report.json`; the old version keeps serving |
| An e5 data model created in the GUI shows Training Failed | The dataset version failed the quality gate (GUI builds enforce it too), or the build hit an error (cron-manager log) | View Results or `quality_report.json` shows the failed check; the model serving its environment didn't change. Fix the dataset, or use another version |
| A new e5 data model shows Undeployed while it trains | Expected: it takes its environment after it passes and loads | Wait for "Model Trained And Deployed" |
| A trained e5 version stays Undeployed after an update | The update was saved with environment Undeployed; a failed version's Settings page shows Undeployed | Choose the environment in the same save as the dataset. Changing only the environment in the GUI fails ("Invalid input ...") and never worked; switch with `builder.rollback` instead |
| `its group already has a version on dataset <n>` | The refresh already built a version from it (failed, switched back, or made by hand) | Publish a fixed dataset version, or delete the failed version in the GUI to try again |
| A training from the GUI doesn't start | The refresh is building a version (its training job is in progress) | Wait a few minutes; it starts when the refresh finishes |
| `is built but stays undeployed` | The old version left its environment while the new one was built (an admin changed it) | Nothing switched; switch by hand with `builder.rollback` if wanted |
| A build loads with "Unsupported ... format" | The classifier image is older than the build (builds with the classifier layer use a newer format) | Deploy the current classifier image |
| Loading fails with "Collection ... is missing" | Qdrant lost the collection | Restore it (above) |
| `chats/classify` returns `out_of_distribution` for a known agency | The agency isn't in the network (`integrated_agencies.part_of_network`) | Expected; the agency sync sets it |
| No `second_opinion` lines | Mode is `off`, or no message landed near the off-topic edge | Check `SECOND_OPINION_MODE` and the warm-up line |
| Mostly `outcome=timeout` | Slow CPU, or the catalogue isn't cached yet | Wait for the warm-up line; give `llm-reranker` more CPUs or raise the limit |
| English or Russian questions flagged off-topic | The cut-off is calibrated on Estonian questions | Known limit |
| One agency often wrong | Too few questions, or questions that don't name their topic | Run the dataset check and add or rewrite questions |

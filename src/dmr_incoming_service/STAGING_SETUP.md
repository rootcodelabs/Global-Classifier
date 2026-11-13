# Setting up DMR in staging

These steps connect the Global Classifier (GC) to DMR in a staging environment. Once they're done, agencies can send chats to the GC and get the classification result back.

To learn how the service works and what it sends and receives, see [README.md](README.md).

The GC needs two containers on the `bykstack` network:

| Container | What it is | Where it comes from |
|---|---|---|
| `dmr-incoming-service` | Receives messages, classifies them and sends results back | This repo (`docker-compose.yml`) |
| `gc-dmr-agent` | The GC's DMR agent: connects to the DMR server, decrypts incoming messages and encrypts outgoing ones | The DMR repo's `dmr-agent` image. You add it to the staging deployment yourself (step 6). |

---

## 1. Before you start

Get these from the other teams first:

- [ ] **The GC registered in CentOps** as an agency, with:
  - an agent ID (its CentOps `clientId`, a UUID);
  - an RSA key pair. CentOps holds the public key. Keep the private key in your secret store, **never in the repo**.
- [ ] **The DMR server's WebSocket URL** for staging.
- [ ] **The `dmr-agent` image** for staging. Use the tag your team publishes, or build it in the DMR repo with `docker build -f apps/dmr-agent/Dockerfile -t dmr-agent:<tag> .`.
- [ ] **Agreement with the sending agencies on the result format** (see [README §7](README.md#7-outgoing-payload-gc--its-dmr-agent)). Their chatbot must recognise `event = "global-classifier-result"`, must not show that message to the end user, and must not send it back to the GC.

The GC also needs these already in place in staging:

- [ ] A deployed **production model**: `get-production-model-id` returns a row, and `triton-production-server` is up.
- [ ] Every agency that can be a classification result is in **`integrated_agencies` with `part_of_network = true`**. `/chats/classify` filters out every other agency.

---

## 2. Set `constants.ini`

Edit the staging `constants.ini`, section `[DSL]`:

```ini
GLOBAL_CLASSIFIER_DMR_AGENT=http://gc-dmr-agent:8077
GLOBAL_CLASSIFIER_DMR_AGENT_ID=<the GC's CentOps clientId>
```
- `GLOBAL_CLASSIFIER_DMR_AGENT` must point to the agent's **service name and port** (step 6).
- `GLOBAL_CLASSIFIER_DMR_AGENT_ID` is empty in the repo on purpose. Set it in staging. While it's empty, the loop guard (which skips messages from the GC itself) is off.
- Check that `GLOBAL_CLASSIFIER_RESQL` and `GLOBAL_CLASSIFIER_RUUTER_PUBLIC` are already correct. The service uses both.
---
## 3. Run the database migration
The migration creates the `dmr_incoming_messages` table (Liquibase changeset `global-classifier-script-v28-dmr-incoming-messages.sql`).
```bash
./migrate.sh
```
`migrate.sh` uses the local database settings (`users_db`, user `postgres`). If the staging database is different, run Liquibase with the staging JDBC URL and credentials instead.
Check that the table exists:
```sql
SELECT count(*) FROM public.dmr_incoming_messages;
```
---
## 4. Deploy the Resql queries and the Ruuter change
Deploy the latest `DSL/` folder:
- `DSL/Resql/global-classifier/POST/*dmr*.sql`: the six new queries.
- `DSL/Ruuter.public/global-classifier/POST/chats/classify.yml`: with no production model, it now returns `503` instead of `500`.
Restart both so they load the new files:
```bash
docker compose restart resql ruuter-public
```
---
## 5. Deploy `dmr-incoming-service`
The service is already defined in `docker-compose.yml`:
```bash
docker compose up -d --build dmr-incoming-service
```
Keep these as they are:
- **No published port.** `/dmr/incoming` has no authentication and trusts `senderId`. Only `gc-dmr-agent` may reach it, over `bykstack`.
- **One worker.** The `Dockerfile` already runs `--workers 1`. The sweeper and the duplicate guard live in the process, so don't scale it beyond **one replica**.
- **`constants.ini` mounted** at `/app/constants.ini` (read-only).
- **`restart: unless-stopped`**.

The defaults below are fine for staging. Change them only if you need to:

| Variable | Default |
|---|---|
| `DMR_STALE_AFTER_SECONDS` | `300` |
| `DMR_SWEEP_INTERVAL_SECONDS` | `60` |
| `DMR_CLASSIFY_TIMEOUT` | `30` s |
| `DMR_AGENT_TIMEOUT` | `10` s |
| `DMR_AGENT_SEND_ATTEMPTS` | `3` |
| `DMR_RESEND_AFTER_SECONDS` | `120` |
| `DMR_RESPONSE_MAX_ATTEMPTS` | `5` |

---

## 6. Deploy the GC DMR agent

Add the agent to the staging compose file, or to an override file used only in staging:

```yaml
  gc-dmr-agent:
    container_name: gc-dmr-agent
    image: dmr-agent:<tag>
    env_file: dmr-agent.env              # AGENT_PRIVATE_KEY=..., from the secret store, not committed
    environment:
      - AGENT_ID=<the GC's CentOps clientId>   # same value as GLOBAL_CLASSIFIER_DMR_AGENT_ID
      - PORT=8077
      - DMR_SERVER_WEBSOCKET_URL=<staging DMR server URL>
      - OUTGOING_MESSAGE_ENDPOINT=http://dmr-incoming-service:8095/dmr/incoming
      - LOGGER_LOG_LEVELS=error,warn,log  # never debug: at debug the agent logs decrypted payloads
    restart: unless-stopped
    networks:
      - bykstack
```
```bash
docker compose up -d gc-dmr-agent
```
Check these:
- The service name `gc-dmr-agent` and port `8077` match `GLOBAL_CLASSIFIER_DMR_AGENT`.
- `AGENT_ID` is the same as `GLOBAL_CLASSIFIER_DMR_AGENT_ID`.
- `dmr-agent.env` is in `.gitignore`, or better, the key is injected from the secret store.
- Don't publish a port for the agent unless your setup needs one.

---

## 7. Change the shared services

These settings affect the existing classify flow too, not only DMR.

- [ ] **DataMapper rate limit.** `data-mapper` allows **30 requests a minute per client IP** by default, and all of Ruuter counts as one IP. Each classification makes one DataMapper call, so 30 a minute is the cap. Set `RATE_LIMIT_PER_MINUTE` on `data-mapper` to match the traffic you expect.
- [ ] **Ruuter logging the question.** Ruuter's `HttpHelper` logs every POST body at INFO (`REQUEST BODY: ...`), and that includes the question sent to `/chats/classify`. Lower that logger's level in the Ruuter configuration. `dmr-incoming-service` itself never logs message content.

---

## 8. Check that it works

1. **Both containers are running and healthy:**
   ```bash
   docker ps --filter name=dmr-incoming-service --filter name=gc-dmr-agent
   docker exec dmr-incoming-service curl -s http://localhost:8095/health
   ```
   The health check should return `{"status":"healthy","service":"dmr-incoming-service"}`.

2. **The agent is connected to DMR:**
   ```bash
   docker logs gc-dmr-agent
   ```
   Look for `Connected to DMR server` and the agent list being received.

3. **Send a test chat** from another staging agency's chatbot to the GC's agent ID. Then check:
   ```bash
   docker logs dmr-incoming-service
   ```
   You should see:
   ```
   DMR message <id> from <sender> accepted (chat <chat id>)
   DMR message <id>: classified, top agency <agency id>
   DMR message <id>: result classified to <sender> SENT
   ```

4. **Look at the row** (no content is stored):
   ```bash
   docker exec dmr-incoming-service curl -s http://localhost:8095/dmr/messages/<message id>
   ```
   Expect `status: CLASSIFIED`, `resultStatus: classified` and `responseStatus: SENT`.

5. **The sending agency got the result:** one message with `event = "global-classifier-result"`, and its `content` naming the agency.

Common problems:

| What you see | Likely cause |
|---|---|
| Nothing in the `dmr-incoming-service` logs | The agent's `OUTGOING_MESSAGE_ENDPOINT` is wrong, the agent isn't connected, or the containers aren't on the same network |
| `FAILED` "classify returned HTTP 503" | No production model is deployed |
| `FAILED` "classify returned HTTP 500" | Triton is down, or DataMapper is rate limiting (`429` in the `data-mapper` logs) |
| `responseStatus: FAILED` "HTTP 400: ..." | The agent rejected the payload. Check that the agent version matches the expected DTO. |
| `responseStatus: FAILED` "HTTP 500: ..." | The agent doesn't know the recipient. Check that the sender is registered in CentOps. |
| `responseStatus: PENDING` "GC DMR agent unreachable" | `GLOBAL_CLASSIFIER_DMR_AGENT` is wrong, or the agent is down. The sweeper sends the result again once the agent is back. |
| `classified` result, but `agencyId` is unknown to the agency | The agency IDs don't match between CentOps and the GC's `integrated_agencies` |

---

## 9. Monitoring and alerts

Alert on these ERROR log lines from `dmr-incoming-service`:

| Log line | Meaning |
|---|---|
| `stale DMR message ... marked FAILED` | A message was acked but never processed (for example, the service crashed). The sender got a `failed` result. |
| `... FAILED for good` | A result couldn't be delivered after every retry |
| `DMR sweeper failed` / `could not check for ...` | The sweeper can't reach Resql |

A query for a dashboard:

```sql
SELECT status, result_status, response_status, count(*)
FROM public.dmr_incoming_messages
WHERE received_at > now() - INTERVAL '1 day'
GROUP BY 1, 2, 3
ORDER BY 4 DESC;
```

Also watch for a growing number of `response_status = 'PENDING'` rows. That means the agent or the DMR server is down.

Decide how long to keep rows in `dmr_incoming_messages`. The table holds chat IDs and routing data, but no message content.

---

## 10. Rollback

1. Stop the agent so no new messages arrive: `docker compose stop gc-dmr-agent`.
2. Stop the service: `docker compose stop dmr-incoming-service`.
3. Only if you need to remove the data too, roll back changeset v28. Its rollback is `DROP TABLE public.dmr_incoming_messages`.

The `classify.yml` change is safe to keep. It only changes the error code from `500` to `503` when there's no production model.

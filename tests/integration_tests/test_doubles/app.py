"""
Test double standing in for three external dependencies of the dataset-generator
module, so the integration test can exercise the real Ruuter DSL, Resql SQL, and
CronManager scripts without needing a real Data Mapper, notifications-node (which
needs OpenSearch), or the real LLM-backed Dataset-Generator service.

Routes implemented:
- POST /hbs/global-classifier/return_random_string  (stands in for Data Mapper)
- GET  /csrf-token                                   (stands in for notifications-node)
- POST /dataset/progress                             (stands in for notifications-node)
- POST /generate-bulk                                (stands in for dataset-gen-service)

Everything POSTed to /generate-bulk and /dataset/progress is recorded in memory and
exposed at GET /_test/calls so the test can assert on what the real DSL/scripts sent,
without needing a real OpenSearch-backed notifications pipeline to read it back from.
"""

import os
import threading
import time

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

CRON_MANAGER_URL = os.environ.get("CRON_MANAGER_URL", "http://cron-manager:8080")
CALLBACK_DELAY_SECONDS = float(os.environ.get("CALLBACK_DELAY_SECONDS", "2"))

_calls = {
    "generate_bulk": [],
    "dataset_progress": [],
}


@app.post("/hbs/global-classifier/return_random_string")
def return_random_string():
    return jsonify({"randomHexString": "deadbeefcafebabe"})


@app.get("/csrf-token")
def csrf_token():
    return jsonify({"csrfToken": "test-csrf-token"})


@app.post("/dataset/progress")
def dataset_progress():
    payload = request.get_json(force=True, silent=True) or {}
    _calls["dataset_progress"].append(payload)
    return jsonify({"ok": True})


@app.post("/generate-bulk")
def generate_bulk():
    payload = request.get_json(force=True, silent=True) or {}
    _calls["generate_bulk"].append(payload)

    session_id = None
    datasets = payload.get("datasets") or []
    if datasets:
        session_id = datasets[0].get("session_id")

    if session_id:
        threading.Thread(target=_fire_callback, args=(session_id,), daemon=True).start()

    return jsonify({"accepted": True, "taskId": session_id}), 200


def _fire_callback(session_id: str) -> None:
    """Simulate the real dataset-gen-service calling back into CronManager
    once generation finishes, the same way callback_format is triggered in prod."""
    time.sleep(CALLBACK_DELAY_SECONDS)
    try:
        requests.post(
            f"{CRON_MANAGER_URL}/execute/callback_formatter/callback_format",
            params={
                "filePath": f"/app/output_datasets/{session_id}.csv",
                "results": "e30=",  # base64 for "{}"; placeholder result payload
                "taskId": session_id,
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        app.logger.error("Failed to fire stub callback: %s", exc)


@app.get("/_test/calls")
def get_calls():
    return jsonify(_calls)


@app.post("/_test/reset")
def reset_calls():
    _calls["generate_bulk"].clear()
    _calls["dataset_progress"].clear()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))

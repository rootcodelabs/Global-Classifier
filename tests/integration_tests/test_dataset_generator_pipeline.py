"""
Integration tests for the dataset-generator module: Ruuter.public's
datasets/progress/* endpoints, the Resql dataset_progress_sessions table, and
the real CronManager scripts (dataset_pipeline_s3.sh, callback_format.sh).

See docker-compose-test.yml / tests/integration_tests/test_doubles for what's
real vs. stubbed in this slice.
"""

import io
import json
import time
import urllib.parse
import zipfile
from datetime import timedelta

import requests


def _create_progress_session(ruuter_public_url: str, dataset_id: int = 1) -> int:
    response = requests.post(
        f"{ruuter_public_url}/datasets/progress/create",
        json={"datasetId": dataset_id, "majorVersion": 1, "minorVersion": 0},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    body = response.json()["response"]
    assert body["operationSuccessful"] is True
    return int(body["sessionId"])


def _fetch_progress_row(postgres_client, session_id: int):
    cursor = postgres_client.cursor()
    try:
        cursor.execute(
            "SELECT generation_status, progress_percentage, process_complete "
            "FROM dataset_progress_sessions WHERE id = %s",
            (session_id,),
        )
        return cursor.fetchone()
    finally:
        cursor.close()


class TestProgressSessionLifecycle:
    """Exercises the real Ruuter DSL + Resql SQL for progress sessions."""

    def test_create_progress_session_persists_to_resql(
        self, ruuter_public_url, postgres_client
    ):
        session_id = _create_progress_session(ruuter_public_url, dataset_id=101)

        row = _fetch_progress_row(postgres_client, session_id)
        assert row is not None
        generation_status, progress_percentage, process_complete = row
        assert generation_status == "Initiating Dataset Generation"
        assert progress_percentage == 0
        assert process_complete is False

    def test_update_progress_session_persists_to_resql(
        self, ruuter_public_url, postgres_client
    ):
        session_id = _create_progress_session(ruuter_public_url, dataset_id=102)

        response = requests.post(
            f"{ruuter_public_url}/datasets/progress/update",
            json={
                "sessionId": session_id,
                "generationStatus": "Downloading Source Datasets",
                "generationMessage": "test update",
                "progressPercentage": 10,
                "processComplete": False,
            },
            timeout=30,
        )
        assert response.status_code == 200, response.text
        assert response.json()["response"]["operationSuccessful"] is True

        row = _fetch_progress_row(postgres_client, session_id)
        assert row is not None
        generation_status, progress_percentage, _ = row
        assert generation_status == "Downloading Source Datasets"
        assert progress_percentage == 10


class TestDatasetPipelineTrigger:
    """Runs the real dataset_pipeline_s3.sh CronManager script end to end,
    up to the point where it calls out to the (stubbed) generator service."""

    def test_pipeline_downloads_from_s3_and_calls_generator(
        self,
        ruuter_public_url,
        cron_manager_url,
        test_doubles_url,
        s3_client,
        s3_internal_client,
        postgres_client,
    ):
        bucket = "test-agency-data"
        if not s3_client.bucket_exists(bucket):
            s3_client.make_bucket(bucket)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("agency_data/sample.txt", "Sample agency support data.")
        zip_buffer.seek(0)

        object_name = "AGENCY1/agency_data.zip"
        s3_client.put_object(
            bucket,
            object_name,
            zip_buffer,
            length=zip_buffer.getbuffer().nbytes,
        )
        # Signed with the in-network hostname/port (seaweedfs:8333) since this URL
        # is fetched by dataset_pipeline_s3.sh running inside the cron-manager
        # container, not by the test process itself.
        presigned_url = s3_internal_client.presigned_get_object(
            bucket, object_name, expires=timedelta(hours=1)
        )

        session_id = _create_progress_session(ruuter_public_url, dataset_id=201)

        signed_urls_payload = [
            {
                "agencyId": "AGENCY1",
                "agencyName": "Test Agency",
                "dataUrl": presigned_url,
            }
        ]
        encoded_signed_urls = urllib.parse.quote(json.dumps(signed_urls_payload))

        requests.post(
            f"{test_doubles_url}/_test/reset",
            timeout=10,
        )

        trigger_response = requests.post(
            f"{cron_manager_url}/execute/dataset_pipeline_scheduler/dataset_pipeline_schedule",
            params={
                "signedUrls": encoded_signed_urls,
                "datasetId": str(session_id),
                "majorVersion": "1",
                "minorVersion": "0",
            },
            timeout=60,
        )
        assert trigger_response.status_code < 500, trigger_response.text

        # The script downloads from SeaweedFS, then POSTs to the stubbed
        # generate-bulk endpoint. Poll for that call to land.
        generate_bulk_calls = []
        for _ in range(30):
            calls = requests.get(f"{test_doubles_url}/_test/calls", timeout=10).json()
            generate_bulk_calls = calls.get("generate_bulk", [])
            if generate_bulk_calls:
                break
            time.sleep(2)

        assert generate_bulk_calls, (
            "dataset_pipeline_s3.sh did not reach the generate-bulk call "
            "within the timeout - check cron-manager logs"
        )
        sent_datasets = generate_bulk_calls[0]["datasets"]
        assert sent_datasets[0]["agency_id"] == "AGENCY1"
        assert sent_datasets[0]["agency_name"] == "Test Agency"

        # dataset_pipeline_s3.sh creates its OWN progress session (using our
        # datasetId as input to /datasets/progress/create), distinct from the
        # one we pre-created above just to get a valid datasetId to pass in.
        # The script's session_id is what it threads through to generate-bulk.
        script_session_id = int(sent_datasets[0]["session_id"])
        row = _fetch_progress_row(postgres_client, script_session_id)
        assert row is not None
        generation_status = row[0]
        assert generation_status in (
            "Calling Dataset Generation",
            "Dataset Generation In progress",
        )

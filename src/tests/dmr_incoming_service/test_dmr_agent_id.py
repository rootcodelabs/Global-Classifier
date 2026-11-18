"""GLOBAL_CLASSIFIER_DMR_AGENT_ID: empty → warning at startup; not a UUID → the service won't start."""

import asyncio
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from dmr_incoming_service import app as app_module
from dmr_incoming_service import settings
from dmr_incoming_service.processor import Processor
from dmr_incoming_service.settings import parse_gc_agent_id
from dmr_test_helpers import GC_ID, make_envelope, result_message

SRC_DIR = Path(__file__).resolve().parents[2]
REPO_CONSTANTS = SRC_DIR.parent / "constants.ini"
EMPTY_WARNING = "GLOBAL_CLASSIFIER_DMR_AGENT_ID is empty"


# ---- parse_gc_agent_id


@pytest.mark.parametrize("value", ["", "   ", None])
def test_empty_id_is_allowed(value):
    assert parse_gc_agent_id(value) == ""


@pytest.mark.parametrize("value", [GC_ID, f"  {GC_ID}  ", GC_ID.upper()])
def test_uuid_is_accepted(value):
    assert parse_gc_agent_id(value) == value.strip()


@pytest.mark.parametrize(
    "value",
    [
        "<the GC's CentOps clientId>",  # the placeholder from STAGING_SETUP.md
        GC_ID[:-1],  # one character short
        GC_ID.replace("-", ""),  # no hyphens
        "global-classifier",
        f"{GC_ID},{GC_ID}",
    ],
)
def test_id_that_is_not_a_uuid_is_refused(value):
    with pytest.raises(RuntimeError, match="is not a UUID"):
        parse_gc_agent_id(value)


def import_settings_with(agent_id, tmp_path):
    """Imports settings in a fresh interpreter with the repo's constants.ini, but this agent ID."""
    constants = REPO_CONSTANTS.read_text(encoding="utf-8")
    constants = re.sub(
        r"(?m)^GLOBAL_CLASSIFIER_DMR_AGENT_ID=.*$",
        f"GLOBAL_CLASSIFIER_DMR_AGENT_ID={agent_id}",
        constants,
    )
    path = tmp_path / "constants.ini"
    path.write_text(constants, encoding="utf-8")
    env = {**os.environ, "CONSTANTS_FILE": str(path), "PYTHONPATH": str(SRC_DIR)}
    return subprocess.run(
        [sys.executable, "-c", "import dmr_incoming_service.settings"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_service_does_not_start_with_an_id_that_is_not_a_uuid(tmp_path):
    result = import_settings_with("<the GC's CentOps clientId>", tmp_path)

    assert result.returncode != 0
    assert "GLOBAL_CLASSIFIER_DMR_AGENT_ID in constants.ini is not a UUID" in (
        result.stderr
    )


@pytest.mark.parametrize("agent_id", ["", GC_ID])
def test_service_starts_with_an_empty_id_or_a_uuid(agent_id, tmp_path):
    result = import_settings_with(agent_id, tmp_path)

    assert result.returncode == 0, result.stderr


# ---- the startup warning


def start_and_stop_the_app():
    async def scenario():
        async with app_module.lifespan(app_module.app):
            pass

    asyncio.run(scenario())


def test_empty_id_is_warned_about_at_startup(monkeypatch, caplog):
    monkeypatch.setattr(settings, "GC_AGENT_ID", "")

    with caplog.at_level(logging.WARNING, logger="dmr_incoming_service"):
        start_and_stop_the_app()

    warnings = [r for r in caplog.records if EMPTY_WARNING in r.getMessage()]
    assert len(warnings) == 1
    assert warnings[0].levelno == logging.WARNING


def test_no_warning_when_the_id_is_set(monkeypatch, caplog):
    monkeypatch.setattr(settings, "GC_AGENT_ID", GC_ID)

    with caplog.at_level(logging.WARNING, logger="dmr_incoming_service"):
        start_and_stop_the_app()

    assert not any(EMPTY_WARNING in r.getMessage() for r in caplog.records)


# ---- why empty is a warning, not fatal


def test_without_the_id_the_gcs_own_result_is_still_not_answered(
    resql, classifier, agent, sleeps
):
    # The loop guard is off, but the echo guard rejects the GC's result coming back to it
    processor = Processor(resql, classifier, agent, gc_agent_id="", sleep=sleeps.append)
    envelope = make_envelope(senderId=GC_ID)
    envelope["payload"]["messages"] = [result_message()]

    _, _, job = processor.accept(envelope)
    processor.process(job)

    assert resql.last("update-dmr-incoming-message")["status"] == "REJECTED"
    assert classifier.calls == []
    assert agent.sent == []

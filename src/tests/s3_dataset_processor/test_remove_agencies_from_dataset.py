"""Tests for remove_agencies_from_dataset."""

from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
import remove_agencies_from_dataset as remover

COLUMNS = ["item_id", "agency_name", "agency_id", "data_item", "dataset_version_id"]


def write_csv(path: Path, rows: list) -> str:
    pd.DataFrame(rows, columns=COLUMNS).to_csv(path, index=False)
    return str(path)


def row(agency_id: str, data_item: str, version: int) -> list:
    return [f"{version}_x", f"Agency {agency_id}", agency_id, data_item, version]


def test_departed_agency_rows_are_removed(tmp_path):
    prev = write_csv(
        tmp_path / "prev.csv",
        [row("TAX", "tax", 7), row("HEALTH", "health", 7), row("POLICE", "police", 7)],
    )
    out = tmp_path / "out.csv"

    removed = remover.remove_agencies(prev, {"POLICE"}, 8, str(out))

    df = pd.read_csv(out, dtype={"agency_id": str})
    assert removed == 1
    assert sorted(df["agency_id"]) == ["HEALTH", "TAX"]


def test_remaining_rows_are_renumbered_for_the_new_version(tmp_path):
    prev = write_csv(
        tmp_path / "prev.csv",
        [row("A1", "a1", 7), row("A2", "a2", 7), row("A3", "a3", 7)],
    )
    out = tmp_path / "out.csv"

    remover.remove_agencies(prev, {"A2"}, 8, str(out))

    df = pd.read_csv(out)
    assert list(df["item_id"]) == ["8_1", "8_2"]
    assert set(df["dataset_version_id"]) == {8}
    assert list(df["data_item"]) == ["a1", "a3"]


def stub_side_effects(monkeypatch, tmp_path, download_status=200):
    """Replace the network calls and return the status mock."""
    monkeypatch.setattr(remover, "OUTPUT_DATA_DIR", tmp_path.as_posix())
    monkeypatch.setattr(remover, "notify_dataset_update", MagicMock())
    monkeypatch.setattr(remover, "upload_csv_to_s3", MagicMock())
    set_status = MagicMock()
    monkeypatch.setattr(remover, "set_generation_status", set_status)

    def download(destination_file_path, **kwargs):
        if download_status == 200:
            write_csv(
                Path(destination_file_path), [row("A1", "a1", 7), row("A2", "a2", 7)]
            )
        return MagicMock(status_code=download_status)

    monkeypatch.setattr(remover.s3_ferry_service, "transfer_file", download)
    return set_status


def test_successful_run_saves_uploads_and_marks_success(monkeypatch, tmp_path):
    set_status = stub_side_effects(monkeypatch, tmp_path)

    remover.remove_agencies_from_dataset(8, 7, {"A2"})

    remover.upload_csv_to_s3.assert_called_once()
    assert remover.upload_csv_to_s3.call_args.args[1] == 8
    set_status.assert_called_once_with(8, "Generation_Success")
    assert not (tmp_path / "8_aggregated.csv").exists()
    assert not (tmp_path / "7_prev.csv").exists()


def test_missing_previous_csv_marks_the_version_failed(monkeypatch, tmp_path):
    set_status = stub_side_effects(monkeypatch, tmp_path, download_status=404)

    with pytest.raises(RuntimeError):
        remover.remove_agencies_from_dataset(8, 7, {"A2"})

    remover.upload_csv_to_s3.assert_not_called()
    set_status.assert_called_once_with(8, "Generation_Failed")


def test_set_generation_status_sends_the_version_and_status(monkeypatch):
    post = MagicMock(return_value=MagicMock(status_code=200))
    monkeypatch.setattr(remover.requests, "post", post)

    remover.set_generation_status(8, "Generation_Success")

    assert post.call_args.kwargs["json"] == {
        "datasetId": "8",
        "generationStatus": "Generation_Success",
    }

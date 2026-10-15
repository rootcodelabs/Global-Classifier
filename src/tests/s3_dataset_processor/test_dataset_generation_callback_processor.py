"""Tests for the dataset merge in dataset_generation_callback_processor."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

PROCESSOR_DIR = Path(__file__).resolve().parents[2] / "s3_dataset_processor"
sys.path.insert(0, str(PROCESSOR_DIR))

import dataset_generation_callback_processor as processor

COLUMNS = ["item_id", "agency_name", "agency_id", "data_item", "dataset_version_id"]


def write_csv(path: Path, rows: list) -> str:
    pd.DataFrame(rows, columns=COLUMNS).to_csv(path, index=False)
    return str(path)


def row(agency_id: str, data_item: str, version: int) -> list:
    return [f"{version}_x", f"Agency {agency_id}", agency_id, data_item, version]


def test_updated_agency_replaces_its_old_rows(tmp_path):
    prev = write_csv(
        tmp_path / "prev.csv",
        [row("A1", "a1 old 1", 7), row("A1", "a1 old 2", 7), row("A2", "a2", 7)],
    )
    curr = write_csv(tmp_path / "curr.csv", [row("A1", "a1 new", 8)])
    out = tmp_path / "out.csv"

    processor.combine_csvs_and_update_ids(prev, curr, 8, str(out), {"A1", "A2"})

    df = pd.read_csv(out, dtype={"agency_id": str})
    assert sorted(df["data_item"]) == ["a1 new", "a2"]


def test_agency_outside_network_is_dropped(tmp_path):
    prev = write_csv(
        tmp_path / "prev.csv",
        [
            row("TAX", "tax", 7),
            row("HEALTH", "health old", 7),
            row("POLICE", "police", 7),
        ],
    )
    curr = write_csv(tmp_path / "curr.csv", [row("HEALTH", "health new", 8)])
    out = tmp_path / "out.csv"

    processor.combine_csvs_and_update_ids(prev, curr, 8, str(out), {"TAX", "HEALTH"})

    df = pd.read_csv(out, dtype={"agency_id": str})
    assert sorted(df["agency_id"]) == ["HEALTH", "TAX"]
    assert sorted(df["data_item"]) == ["health new", "tax"]


def test_merged_rows_are_renumbered_for_the_new_version(tmp_path):
    prev = write_csv(tmp_path / "prev.csv", [row("A1", "a1", 7), row("A2", "a2", 7)])
    curr = write_csv(tmp_path / "curr.csv", [row("A3", "a3", 8)])
    out = tmp_path / "out.csv"

    processor.combine_csvs_and_update_ids(prev, curr, 8, str(out), {"A1", "A3"})

    df = pd.read_csv(out)
    assert list(df["item_id"]) == ["8_1", "8_2"]
    assert set(df["dataset_version_id"]) == {8}


def test_numeric_agency_ids_match_the_network_list():
    df = pd.DataFrame({"agency_id": [101, 202], "data_item": ["a", "b"]})

    filtered = processor.keep_agencies_in_network(df, {"101"})

    assert list(filtered["data_item"]) == ["a"]


def test_get_agencies_in_network_reads_resql_rows(monkeypatch):
    response = MagicMock(status_code=200)
    response.json.return_value = [{"agencyId": "A1"}, {"agencyId": "A2"}]
    monkeypatch.setattr(processor.requests, "post", MagicMock(return_value=response))

    assert processor.get_agencies_in_network() == {"A1", "A2"}


def test_get_agencies_in_network_fails_when_resql_fails(monkeypatch):
    response = MagicMock(status_code=500, text="error")
    monkeypatch.setattr(processor.requests, "post", MagicMock(return_value=response))

    with pytest.raises(RuntimeError):
        processor.get_agencies_in_network()


def test_run_stops_when_network_list_cannot_be_fetched(monkeypatch, tmp_path):
    curr = Path(write_csv(tmp_path / "3.csv", [row("A1", "a1", 3)])).as_posix()
    monkeypatch.setattr(
        processor,
        "get_agencies_in_network",
        MagicMock(side_effect=RuntimeError("down")),
    )
    upload = MagicMock()
    monkeypatch.setattr(processor, "upload_csv_to_s3", upload)

    with pytest.raises(RuntimeError):
        processor.process_callback_background(curr, "", 1)

    upload.assert_not_called()


def stub_run_side_effects(monkeypatch, tmp_path):
    """Replace the network calls around the merge and return the S3 transfer mock."""
    monkeypatch.setattr(processor, "OUTPUT_DATA_DIR", tmp_path.as_posix())
    monkeypatch.setattr(
        processor, "get_agencies_in_network", MagicMock(return_value={"A1", "A2"})
    )
    for name in [
        "notify_dataset_update",
        "upload_csv_to_s3",
        "send_status_update",
        "cleanup_temporary_files",
        "notify_progress_uploading_to_s3",
    ]:
        monkeypatch.setattr(processor, name, MagicMock())
    transfer = MagicMock(return_value=MagicMock(status_code=200))
    monkeypatch.setattr(processor.s3_ferry_service, "transfer_file", transfer)
    return transfer


def test_merge_skips_a_failed_version_in_between(monkeypatch, tmp_path):
    transfer = stub_run_side_effects(monkeypatch, tmp_path)
    monkeypatch.setattr(
        processor, "get_previous_successful_dataset_id", MagicMock(return_value=7)
    )

    def download_version_7(destination_file_path, **kwargs):
        write_csv(
            Path(destination_file_path), [row("A1", "a1 old", 7), row("A2", "a2", 7)]
        )
        return MagicMock(status_code=200)

    transfer.side_effect = download_version_7
    curr = Path(write_csv(tmp_path / "9.csv", [row("A1", "a1 new", 9)])).as_posix()

    processor.process_callback_background(curr, "", 1)

    assert transfer.call_args.kwargs["source_file_path"] == (
        "datasets/7/aggregated_dataset.csv"
    )
    df = pd.read_csv(tmp_path / "9_aggregated.csv")
    assert sorted(df["data_item"]) == ["a1 new", "a2"]


def test_no_successful_version_uses_current_csv_only(monkeypatch, tmp_path):
    transfer = stub_run_side_effects(monkeypatch, tmp_path)
    monkeypatch.setattr(
        processor, "get_previous_successful_dataset_id", MagicMock(return_value=None)
    )
    curr = Path(write_csv(tmp_path / "5.csv", [row("A1", "a1", 5)])).as_posix()

    processor.process_callback_background(curr, "", 1)

    transfer.assert_not_called()
    df = pd.read_csv(tmp_path / "5_aggregated.csv")
    assert list(df["data_item"]) == ["a1"]


def test_run_stops_when_previous_version_cannot_be_looked_up(monkeypatch, tmp_path):
    stub_run_side_effects(monkeypatch, tmp_path)
    monkeypatch.setattr(
        processor,
        "get_previous_successful_dataset_id",
        MagicMock(side_effect=RuntimeError("down")),
    )
    curr = Path(write_csv(tmp_path / "9.csv", [row("A1", "a1", 9)])).as_posix()

    with pytest.raises(RuntimeError):
        processor.process_callback_background(curr, "", 1)

    processor.upload_csv_to_s3.assert_not_called()


@pytest.mark.parametrize(
    ("rows", "expected"), [([{"id": 7}], 7), ([], None)], ids=["found", "none"]
)
def test_get_previous_successful_dataset_id_reads_resql_rows(
    monkeypatch, rows, expected
):
    response = MagicMock(status_code=200)
    response.json.return_value = rows
    post = MagicMock(return_value=response)
    monkeypatch.setattr(processor.requests, "post", post)

    assert processor.get_previous_successful_dataset_id(9) == expected
    assert post.call_args.kwargs["json"] == {"datasetId": 9}


def test_get_previous_successful_dataset_id_fails_when_resql_fails(monkeypatch):
    response = MagicMock(status_code=500, text="error")
    monkeypatch.setattr(processor.requests, "post", MagicMock(return_value=response))

    with pytest.raises(RuntimeError):
        processor.get_previous_successful_dataset_id(9)

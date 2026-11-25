from datetime import datetime, timezone
import os

from ml.ingestion.live_loop import MOSDACDownloader


def test_poll_for_new_data_discovers_new_file(tmp_path):
    downloader = MOSDACDownloader(download_dir=str(tmp_path))
    data_file = tmp_path / "observation.nc"
    data_file.write_bytes(b"new")

    assert downloader.poll_for_new_data() == str(data_file)


def test_poll_for_new_data_ignores_unchanged_file(tmp_path):
    downloader = MOSDACDownloader(download_dir=str(tmp_path))
    data_file = tmp_path / "observation.nc"
    data_file.write_bytes(b"unchanged")
    downloader._update_last_processed(data_file.stat().st_mtime)
    downloader.last_processed = downloader._get_last_processed()

    assert downloader.poll_for_new_data() is None


def test_poll_for_new_data_discovers_updated_file(tmp_path):
    downloader = MOSDACDownloader(download_dir=str(tmp_path))
    data_file = tmp_path / "observation.nc"
    data_file.write_bytes(b"original")
    original_mtime = data_file.stat().st_mtime
    downloader._update_last_processed(original_mtime)
    downloader.last_processed = downloader._get_last_processed()

    updated_mtime = original_mtime + 10
    data_file.write_bytes(b"updated")
    os.utime(data_file, (updated_mtime, updated_mtime))

    assert downloader.poll_for_new_data() == str(data_file)


def test_legacy_iso_timestamp_is_normalized_to_epoch(tmp_path):
    downloader = MOSDACDownloader(download_dir=str(tmp_path))
    timestamp = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    (tmp_path / downloader.STATE_FILENAME).write_text(timestamp.isoformat(), encoding="utf-8")

    assert downloader._get_last_processed() == timestamp.timestamp()

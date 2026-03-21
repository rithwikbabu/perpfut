import json

from perpfut.run_history import find_latest_run, load_run_state, summarize_runs


def test_run_history_finds_latest_matching_run(tmp_path) -> None:
    older = tmp_path / "20260101T000000000000Z_old"
    older.mkdir()
    (older / "manifest.json").write_text(
        json.dumps({"run_id": older.name, "mode": "paper", "product_id": "BTC-PERP-INTX"}),
        encoding="utf-8",
    )
    (older / "state.json").write_text(json.dumps({"run_id": older.name}), encoding="utf-8")

    newer = tmp_path / "20260102T000000000000Z_new"
    newer.mkdir()
    (newer / "manifest.json").write_text(
        json.dumps({"run_id": newer.name, "mode": "live", "product_id": "BTC-PERP-INTX"}),
        encoding="utf-8",
    )
    (newer / "state.json").write_text(json.dumps({"run_id": newer.name}), encoding="utf-8")

    latest = find_latest_run(tmp_path, mode="live", product_id="BTC-PERP-INTX")

    assert latest == newer
    assert load_run_state(latest)["run_id"] == newer.name


def test_summarize_runs_includes_resume_metadata(tmp_path) -> None:
    run_dir = tmp_path / "20260102T000000000000Z_new"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_dir.name,
                "mode": "live",
                "product_id": "BTC-PERP-INTX",
                "resumed_from_run_id": "older-run",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "state.json").write_text(json.dumps({"run_id": run_dir.name}), encoding="utf-8")

    summaries = summarize_runs(tmp_path, limit=5)

    assert summaries[0]["resumed_from_run_id"] == "older-run"

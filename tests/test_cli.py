"""Tests for the combined command-line entry point."""

from __future__ import annotations

from pathlib import Path

from image_workflow.cli import main


def test_import_subcommand_dry_run(source: Path, tmp_path: Path, make_image, capsys):
    src = make_image("incoming/IMG_0001.JPG")
    archive = tmp_path / "archive"

    exit_code = main(
        [
            "import",
            str(source),
            "--destination",
            str(archive),
            "--dry-run",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "would move" in output
    assert src.exists()
    assert not archive.exists()

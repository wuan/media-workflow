"""Tests for the combined command-line entry point."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from image_workflow import duplicates, fix_times
from image_workflow.cli import ROOT_ENV, SOURCE_ENV, build_parser, main
from image_workflow.importer import import_images


def _write_jpeg(path: Path, color=(10, 20, 30)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (24, 18), color).save(path, "JPEG")
    return path


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


def test_import_uses_source_env(monkeypatch, tmp_path: Path, make_image, capsys):
    src = make_image("incoming/IMG_0001.JPG")
    monkeypatch.setenv(SOURCE_ENV, str(src.parent))

    exit_code = main(["import", "--dry-run"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "would move" in output
    assert str(src) in output


def test_import_source_argument_overrides_env(
    monkeypatch, source: Path, tmp_path: Path, make_image, capsys
):
    src = make_image("incoming/IMG_0001.JPG")
    env_source = tmp_path / "env_incoming"
    env_source.mkdir()
    monkeypatch.setenv(SOURCE_ENV, str(env_source))

    exit_code = main(
        [
            "import",
            str(source),
            "--destination",
            str(tmp_path / "archive"),
            "--dry-run",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "would move" in output
    assert str(src) in output


def test_import_destination_uses_root_env(
    monkeypatch, source: Path, tmp_path: Path, make_image, capsys
):
    make_image("incoming/IMG_0001.JPG")
    archive = tmp_path / "archive"
    monkeypatch.setenv(ROOT_ENV, str(archive))

    exit_code = main(["import", str(source), "--dry-run"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert str(archive) in output


def test_import_destination_argument_overrides_root_env(
    monkeypatch, source: Path, tmp_path: Path, make_image, capsys
):
    make_image("incoming/IMG_0001.JPG")
    env_archive = tmp_path / "env_archive"
    explicit_archive = tmp_path / "explicit_archive"
    monkeypatch.setenv(ROOT_ENV, str(env_archive))

    exit_code = main(
        [
            "import",
            str(source),
            "--destination",
            str(explicit_archive),
            "--dry-run",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert str(explicit_archive) in output
    assert str(env_archive) not in output


def test_duplicates_uses_root_env(monkeypatch, tmp_path: Path, capsys):
    root = tmp_path / "photos"
    _write_jpeg(root / "beach.jpg")
    _write_jpeg(root / "beach_1.jpg")
    monkeypatch.setenv(ROOT_ENV, str(root))

    exit_code = main(["duplicates"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "would delete" in output
    assert "beach_1.jpg" in output


def test_duplicates_root_argument_overrides_env(monkeypatch, tmp_path: Path, capsys):
    env_root = tmp_path / "env_photos"
    _write_jpeg(env_root / "beach.jpg")
    _write_jpeg(env_root / "beach_1.jpg")
    explicit_root = tmp_path / "explicit_photos"
    explicit_root.mkdir()
    monkeypatch.setenv(ROOT_ENV, str(env_root))

    exit_code = main(["duplicates", str(explicit_root)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "would delete" not in output


def test_fix_times_uses_root_env_for_root_and_destination(
    monkeypatch, tmp_path: Path, capsys
):
    root = tmp_path / "library"
    _write_jpeg(root / "photo.jpg")
    monkeypatch.setenv(ROOT_ENV, str(root))

    args = build_parser().parse_args(["fix-times"])
    assert args.root == str(root)
    assert args.destination == str(root)

    exit_code = main(["fix-times", "--dry-run"])

    assert exit_code == 0
    assert "1 JPEG file(s)" in capsys.readouterr().err


def test_fix_times_arguments_override_root_env(monkeypatch, tmp_path: Path):
    env_root = tmp_path / "env_library"
    explicit_root = tmp_path / "explicit_fix"
    explicit_destination = tmp_path / "explicit_archive"
    monkeypatch.setenv(ROOT_ENV, str(env_root))

    args = build_parser().parse_args(
        [
            "fix-times",
            str(explicit_root),
            "--destination",
            str(explicit_destination),
        ]
    )

    assert args.root == str(explicit_root)
    assert args.destination == str(explicit_destination)


def test_missing_import_source_error_names_env(monkeypatch, capsys):
    monkeypatch.delenv(SOURCE_ENV, raising=False)

    with pytest.raises(SystemExit) as excinfo:
        main(["import"])

    assert excinfo.value.code == 2
    assert SOURCE_ENV in capsys.readouterr().err


def test_missing_fix_times_root_error_names_env(monkeypatch, capsys):
    monkeypatch.delenv(ROOT_ENV, raising=False)

    with pytest.raises(SystemExit) as excinfo:
        main(["fix-times"])

    assert excinfo.value.code == 2
    assert ROOT_ENV in capsys.readouterr().err


def test_empty_source_env_is_treated_as_unset(monkeypatch, capsys):
    monkeypatch.setenv(SOURCE_ENV, "")

    with pytest.raises(SystemExit) as excinfo:
        main(["import"])

    assert excinfo.value.code == 2
    assert SOURCE_ENV in capsys.readouterr().err


def test_empty_root_env_falls_back_to_current_directory(monkeypatch):
    monkeypatch.setenv(ROOT_ENV, "")

    assert build_parser().parse_args(["duplicates"]).root == "."
    assert build_parser().parse_args(["import", "somewhere"]).destination == "."


def test_library_api_and_modules_ignore_environment(
    monkeypatch, source: Path, tmp_path: Path, make_image, capsys
):
    make_image("incoming/IMG_0001.JPG")
    monkeypatch.setenv(SOURCE_ENV, str(tmp_path / "bogus_source"))
    monkeypatch.setenv(ROOT_ENV, str(tmp_path / "bogus_root"))

    archive = tmp_path / "archive"
    results = import_images(source, destination=archive, dry_run=True)
    assert results[0].destination is not None
    assert archive in results[0].destination.parents

    fix_root = tmp_path / "fix_root"
    _write_jpeg(fix_root / "photo.jpg")
    fix_times.fix_times(fix_root, destination=archive, dry_run=True)

    dup_root = tmp_path / "dup_root"
    _write_jpeg(dup_root / "beach.jpg")
    _write_jpeg(dup_root / "beach_1.jpg")
    exit_code = duplicates.main([str(dup_root)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "would delete" in output
    assert "beach_1.jpg" in output

"""Smoke tests for the packaged duplicate finder."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from image_workflow import duplicates


def _write_jpeg(path: Path, color=(10, 20, 30)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (24, 18), color).save(path, "JPEG")
    return path


def test_identical_copies_are_reported_in_dry_run(tmp_path: Path, capsys):
    root = tmp_path / "photos"
    original = _write_jpeg(root / "beach.jpg")
    copy = _write_jpeg(root / "beach_1.jpg")

    exit_code = duplicates.main([str(root)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "would delete" in output
    assert "beach_1.jpg" in output
    assert original.exists()
    assert copy.exists()


def test_apply_removes_identical_copy(tmp_path: Path, capsys):
    root = tmp_path / "photos"
    original = _write_jpeg(root / "beach.jpg")
    copy = _write_jpeg(root / "beach_1.jpg")

    exit_code = duplicates.main([str(root), "--apply"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "removed" in output
    assert original.exists()
    assert not copy.exists()


def test_trash_moves_copy_into_mirrored_dtrash_tree(tmp_path: Path, capsys):
    root = tmp_path / "photos" / "2024"
    original = _write_jpeg(root / "beach.jpg")
    copy = _write_jpeg(root / "beach_1.jpg")

    exit_code = duplicates.main([str(tmp_path / "photos"), "--apply", "--trash"])

    capsys.readouterr()
    trashed = tmp_path / "photos" / ".dtrash" / "2024" / "beach_1.jpg"
    assert exit_code == 0
    assert original.exists()
    assert not copy.exists()
    assert trashed.exists()


def test_identical_video_copies_are_reported_in_dry_run(
    tmp_path: Path, make_video, capsys
):
    root = tmp_path / "videos"
    original = make_video("videos/clip.mp4")
    copy = make_video("videos/clip_1.mp4")

    exit_code = duplicates.main([str(root)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "would delete" in output
    assert "clip_1.mp4" in output
    assert original.exists()
    assert copy.exists()


def test_apply_removes_identical_video_copy(tmp_path: Path, make_video, capsys):
    root = tmp_path / "videos"
    original = make_video("videos/clip.mp4")
    copy = make_video("videos/clip_1.mp4")

    exit_code = duplicates.main([str(root), "--apply"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "removed" in output
    assert original.exists()
    assert not copy.exists()


def test_trash_moves_video_copy_into_mirrored_dtrash_tree(
    tmp_path: Path, make_video, capsys
):
    original = make_video("videos/2025/clip.mp4")
    copy = make_video("videos/2025/clip_1.mp4")

    exit_code = duplicates.main([str(tmp_path / "videos"), "--apply", "--trash"])

    capsys.readouterr()
    trashed = tmp_path / "videos" / ".dtrash" / "2025" / "clip_1.mp4"
    assert exit_code == 0
    assert original.exists()
    assert not copy.exists()
    assert trashed.exists()


def test_fuzzy_run_skips_video_pixel_comparison(tmp_path: Path, make_video, capsys):
    root = tmp_path / "videos"
    original = make_video("videos/clip.mp4")
    copy = make_video("videos/clip_1.mp4")

    exit_code = duplicates.main([str(root), "--apply", "--fuzzy"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "removed" in captured.out
    assert "cannot read image" not in captured.err
    assert original.exists()
    assert not copy.exists()


def test_video_extensions_must_match(tmp_path: Path, make_video, capsys):
    root = tmp_path / "videos"
    original = make_video("videos/clip.mp4")
    copy = make_video("videos/clip_1.mov")

    exit_code = duplicates.main([str(root)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "would delete" not in output
    assert original.exists()
    assert copy.exists()


def test_unrelated_video_prefix_is_not_a_candidate(tmp_path: Path, make_video, capsys):
    root = tmp_path / "videos"
    original = make_video("videos/clip.mp4")
    extra = make_video("videos/clip_extra.mp4")

    exit_code = duplicates.main([str(root)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "would delete" not in output
    assert original.exists()
    assert extra.exists()

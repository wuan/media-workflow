"""Tests for the Python port of the original import.sh exiftool command."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

from media_workflow import import_images, sanitize_component
from media_workflow.importer import read_metadata

BASE_NAME = "20240715_123456_Canon_EOS-5D.jpg"


def test_imports_photo_into_year_month_tree(source: Path, tmp_path: Path, make_image):
    src = make_image("incoming/IMG_0001.JPG")
    os.utime(src, ns=(1_600_000_000_000_000_000, 1_600_000_000_000_000_000))
    original_bytes = src.read_bytes()
    original_mtime = src.stat().st_mtime_ns

    archive = tmp_path / "archive"
    results = import_images(source, archive)

    assert len(results) == 1
    result = results[0]
    target = archive / "2024" / "07" / BASE_NAME

    assert result.status == "moved"
    assert result.source == src
    assert result.destination == target
    assert not src.exists()
    assert target.exists()
    assert target.read_bytes() == original_bytes
    assert target.stat().st_mtime_ns == original_mtime


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"make": None}, "missing Make"),
        ({"model": None}, "missing Model"),
        ({"datetime_original": None}, "missing DateTimeOriginal"),
        ({"make": ""}, "missing Make"),
        ({"model": "   "}, "missing Model"),
    ],
)
def test_files_missing_required_tags_are_left_alone(
    source: Path, tmp_path: Path, make_image, kwargs, reason
):
    src = make_image("incoming/IMG_0001.JPG", **kwargs)

    results = import_images(source, tmp_path / "archive")

    assert len(results) == 1
    assert results[0].status == "skipped"
    assert reason in (results[0].reason or "")
    assert src.exists()
    assert not (tmp_path / "archive").exists()


def test_file_with_no_exif_is_skipped(source: Path, tmp_path: Path, make_image):
    src = make_image(
        "incoming/plain.jpg",
        make=None,
        model=None,
        datetime_original=None,
    )

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "skipped"
    assert "missing Make, Model, DateTimeOriginal" in (results[0].reason or "")
    assert src.exists()


@pytest.mark.parametrize(
    ("subsec", "expected_name"),
    [
        (None, "20240715_123456_Canon_EOS-5D.jpg"),
        ("123", "20240715_123456.123_Canon_EOS-5D.jpg"),
        ("0123", "20240715_123456.0123_Canon_EOS-5D.jpg"),
        ("", "20240715_123456_Canon_EOS-5D.jpg"),
    ],
)
def test_subseconds_are_appended_verbatim(
    source: Path, tmp_path: Path, make_image, subsec, expected_name
):
    make_image("incoming/IMG_0001.JPG", subsec=subsec)

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "moved"
    assert results[0].destination.name == expected_name


def test_subseconds_can_be_disabled(source: Path, tmp_path: Path, make_image):
    make_image("incoming/IMG_0001.JPG", subsec="123")

    results = import_images(source, tmp_path / "archive", include_subseconds=False)

    assert results[0].status == "moved"
    assert results[0].destination.name == BASE_NAME


def test_dry_run_reserves_names_for_collisions_within_the_batch(
    source: Path, tmp_path: Path, make_image
):
    for name in ("a.jpg", "b.jpg"):
        make_image(f"incoming/{name}")

    results = import_images(source, tmp_path / "archive", dry_run=True)

    assert [result.destination.name for result in results] == [
        BASE_NAME,
        "20240715_123456_Canon_EOS-5D_1.jpg",
    ]


def test_spaces_and_repeated_hyphens_are_normalized(
    source: Path, tmp_path: Path, make_image
):
    make_image(
        "incoming/IMG_0001.JPG",
        make="Canon  Inc.",
        model="EOS  5D Mark--IV",
    )

    results = import_images(source, tmp_path / "archive")

    assert results[0].destination.name == (
        "20240715_123456_Canon-Inc._EOS-5D-Mark-IV.jpg"
    )


def test_sanitize_component_matches_exiftool_rules():
    assert sanitize_component("Canon  Inc.") == "Canon-Inc."
    assert sanitize_component("EOS  5D Mark--IV") == "EOS-5D-Mark-IV"
    assert sanitize_component("A - B") == "A-B"
    assert sanitize_component("A/B\\C") == "A-B-C"


@pytest.mark.parametrize("suffix", [".jpg", ".jpeg", ".JPG", ".Jpeg"])
def test_jpeg_extension_is_normalized_to_jpg(
    source: Path, tmp_path: Path, make_image, suffix
):
    make_image(f"incoming/photo{suffix}")

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "moved"
    assert results[0].destination.suffix == ".jpg"
    assert results[0].destination.name == BASE_NAME


def test_png_keeps_exiftool_file_type_extension(
    source: Path, tmp_path: Path, make_image
):
    make_image("incoming/photo.png")

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "moved"
    assert results[0].destination.name == "20240715_123456_Canon_EOS-5D.png"


def test_collision_with_existing_files_uses_next_copy_number(
    source: Path, tmp_path: Path, make_image
):
    make_image("incoming/IMG_0001.JPG")
    archive = tmp_path / "archive"
    target_dir = archive / "2024" / "07"
    target_dir.mkdir(parents=True)
    (target_dir / BASE_NAME).write_bytes(b"already here")
    (target_dir / "20240715_123456_Canon_EOS-5D_1.jpg").write_bytes(b"also here")

    results = import_images(source, archive)

    assert results[0].status == "moved"
    assert results[0].destination.name == "20240715_123456_Canon_EOS-5D_2.jpg"
    assert results[0].destination.exists()
    assert (target_dir / BASE_NAME).read_bytes() == b"already here"


def test_collision_within_one_run_numbers_each_extra_file(
    source: Path, tmp_path: Path, make_image
):
    for name in ("a.jpg", "b.jpg", "c.jpg"):
        make_image(f"incoming/{name}")

    results = import_images(source, tmp_path / "archive")

    assert [result.status for result in results] == ["moved", "moved", "moved"]
    assert [result.destination.name for result in results] == [
        BASE_NAME,
        "20240715_123456_Canon_EOS-5D_1.jpg",
        "20240715_123456_Canon_EOS-5D_2.jpg",
    ]


def test_file_already_at_computed_destination_is_unchanged(tmp_path: Path, make_image):
    src = make_image(f"archive/2024/07/{BASE_NAME}")
    archive = tmp_path / "archive"
    source_dir = archive / "2024" / "07"

    results = import_images(source_dir, archive)

    assert len(results) == 1
    assert results[0].status == "unchanged"
    assert results[0].destination == src
    assert src.exists()
    assert not (source_dir / "20240715_123456_Canon_EOS-5D_1.jpg").exists()


def test_dry_run_does_not_create_or_move_anything(
    source: Path, tmp_path: Path, make_image
):
    src = make_image("incoming/IMG_0001.JPG")
    archive = tmp_path / "archive"

    results = import_images(source, archive, dry_run=True)

    assert results[0].status == "would_move"
    assert results[0].destination == archive / "2024" / "07" / BASE_NAME
    assert src.exists()
    assert not results[0].destination.exists()
    assert not archive.exists()


def test_recursion_is_opt_in_like_exiftool(source: Path, tmp_path: Path, make_image):
    nested = make_image("incoming/nested/IMG_0001.JPG")
    archive = tmp_path / "archive"

    assert import_images(source, archive) == []
    assert nested.exists()

    results = import_images(source, archive, recursive=True)

    assert len(results) == 1
    assert results[0].status == "moved"
    assert results[0].destination == archive / "2024" / "07" / BASE_NAME
    assert not nested.exists()


@pytest.mark.parametrize(
    "bad_date",
    ["not-a-date", "2024:02:30 10:00:00", "0000:01:01 00:00:00"],
)
def test_invalid_datetime_original_is_skipped(
    source: Path, tmp_path: Path, make_image, bad_date
):
    src = make_image("incoming/IMG_0001.JPG", datetime_original=bad_date)

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "skipped"
    assert "invalid DateTimeOriginal" in (results[0].reason or "")
    assert src.exists()


def test_timezone_offset_is_ignored_like_exiftool(
    source: Path, tmp_path: Path, make_image
):
    make_image(
        "incoming/IMG_0001.JPG",
        datetime_original="2021:03:04 05:06:07+02:00",
    )

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "moved"
    assert results[0].destination == (
        tmp_path / "archive" / "2021" / "03" / "20210304_050607_Canon_EOS-5D.jpg"
    )


def test_metadata_in_ifd0_is_also_read(source: Path, tmp_path: Path, make_image):
    make_image("incoming/IMG_0001.JPG", exif_ifd=False)

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "moved"
    assert results[0].destination.name == BASE_NAME


def test_non_image_files_are_skipped(source: Path, tmp_path: Path):
    notes = source / "notes.txt"
    notes.write_text("not a photo")

    results = import_images(source, tmp_path / "archive")

    assert len(results) == 1
    assert results[0].status == "skipped"
    assert "not a supported image" in (results[0].reason or "")
    assert notes.exists()


def test_corrupt_jpeg_is_skipped(source: Path, tmp_path: Path):
    bad = source / "bad.jpg"
    bad.write_bytes(b"this is not a JPEG")

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "skipped"
    assert bad.exists()


def test_destination_defaults_to_current_directory(
    source: Path, tmp_path: Path, make_image, monkeypatch
):
    make_image("incoming/IMG_0001.JPG")
    monkeypatch.chdir(tmp_path)

    results = import_images(source)

    assert results[0].status == "moved"
    assert results[0].destination == tmp_path / "2024" / "07" / BASE_NAME
    assert results[0].destination.exists()


def test_missing_source_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        import_images(tmp_path / "does-not-exist", tmp_path / "archive")


def test_source_may_be_a_single_file(source: Path, tmp_path: Path, make_image):
    src = make_image("incoming/IMG_0001.JPG")

    results = import_images(src, tmp_path / "archive")

    assert results[0].status == "moved"
    assert not src.exists()
    assert results[0].destination == tmp_path / "archive" / "2024" / "07" / BASE_NAME


def test_image_data_and_exif_survive_the_rename(
    source: Path, tmp_path: Path, make_image
):
    src = make_image("incoming/IMG_0001.JPG", subsec="999")
    with Image.open(src) as image:
        assert image.getexif()[271] == "Canon"

    results = import_images(source, tmp_path / "archive")

    target = results[0].destination
    with Image.open(target) as image:
        assert image.getexif()[271] == "Canon"
        assert image.getexif()[272] == "EOS 5D"
        exif_ifd = image.getexif().get_ifd(0x8769)
        assert exif_ifd[36867] == "2024:07:15 12:34:56"
        assert exif_ifd[37521] == "999"


def test_imports_pixel_video_into_year_month_tree(
    source: Path, tmp_path: Path, make_video
):
    src = make_video("incoming/PXL_20250809_194948618.TS.mp4")
    os.utime(src, ns=(1_600_000_000_000_000_000, 1_600_000_000_000_000_000))
    original_bytes = src.read_bytes()
    original_mtime = src.stat().st_mtime_ns

    archive = tmp_path / "archive"
    results = import_images(source, archive)

    target = archive / "2025" / "08" / "20250809_194948.618_Google_Pixel-6.mp4"
    assert len(results) == 1
    assert results[0].status == "moved"
    assert results[0].source == src
    assert results[0].destination == target
    assert not src.exists()
    assert target.read_bytes() == original_bytes
    assert target.stat().st_mtime_ns == original_mtime


def test_video_falls_back_to_mvhd_when_filename_has_no_timestamp(
    source: Path, tmp_path: Path, make_video
):
    make_video("incoming/IMG_1234.MOV")

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "moved"
    assert results[0].destination.name == "20250809_195121_Google_Pixel-6.mov"


def test_invalid_filename_timestamp_falls_back_to_mvhd(
    source: Path, tmp_path: Path, make_video
):
    make_video("incoming/PXL_20241399_194948618.mp4")

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "moved"
    assert results[0].destination.name == "20250809_195121_Google_Pixel-6.mp4"


def test_mvhd_version_1_is_read(source: Path, tmp_path: Path, make_video):
    make_video("incoming/IMG_1234.MOV", version=1)

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "moved"
    assert results[0].destination.name == "20250809_195121_Google_Pixel-6.mov"


def test_out_of_range_mvhd_is_skipped(source: Path, tmp_path: Path, make_video):
    src = make_video("incoming/IMG_1234.MOV", version=1, creation_seconds=2**63)

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "skipped"
    assert "missing video timestamp" in (results[0].reason or "")
    assert src.exists()


def test_video_missing_make_model_is_skipped(source: Path, tmp_path: Path, make_video):
    src = make_video(
        "incoming/clip.mp4",
        android_make=None,
        android_model=None,
    )

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "skipped"
    assert "missing Make, Model" in (results[0].reason or "")
    assert src.exists()


def test_video_missing_timestamp_is_skipped(source: Path, tmp_path: Path, make_video):
    src = make_video("incoming/clip.mp4", creation_time=None)

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "skipped"
    assert "missing video timestamp" in (results[0].reason or "")
    assert src.exists()


def test_unsupported_video_container_is_skipped(source: Path, tmp_path: Path):
    clip = source / "clip.mkv"
    clip.write_bytes(b"not an ISO-BMFF file")

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "skipped"
    assert "not a supported video container" in (results[0].reason or "")
    assert clip.exists()


@pytest.mark.parametrize(
    "content",
    [
        b"not an mp4",
        b"\x00\x00\x00\x04ftyp",
        b"\x00\x00\x00\x10ftyp" + b"isom",
    ],
)
def test_invalid_mp4_content_is_skipped(source: Path, tmp_path: Path, content: bytes):
    bad = source / "bad.mp4"
    bad.write_bytes(content)

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "skipped"
    assert "not a supported video" in (results[0].reason or "")
    assert bad.exists()


def test_video_without_video_track_is_skipped(source: Path, tmp_path: Path, make_video):
    src = make_video("incoming/clip.mp4", video_track=False)

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "skipped"
    assert "not a supported video" in (results[0].reason or "")
    assert src.exists()


def test_video_without_ftyp_is_skipped(source: Path, tmp_path: Path, make_video):
    src = make_video("incoming/clip.mp4", ftyp=False)

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "skipped"
    assert "not a supported video" in (results[0].reason or "")
    assert src.exists()


def test_video_dry_run_does_not_create_or_move_anything(
    source: Path, tmp_path: Path, make_video
):
    src = make_video("incoming/PXL_20250809_194948618.TS.mp4")
    archive = tmp_path / "archive"

    results = import_images(source, archive, dry_run=True)

    assert results[0].status == "would_move"
    assert results[0].destination == (
        archive / "2025" / "08" / "20250809_194948.618_Google_Pixel-6.mp4"
    )
    assert src.exists()
    assert not archive.exists()


def test_video_collision_numbering(source: Path, tmp_path: Path, make_video):
    make_video("incoming/PXL_20250809_194948618.TS.mp4")
    archive = tmp_path / "archive"
    target_dir = archive / "2025" / "08"
    target_dir.mkdir(parents=True)
    existing = target_dir / "20250809_194948.618_Google_Pixel-6.mp4"
    existing.write_bytes(b"already here")

    results = import_images(source, archive)

    assert results[0].status == "moved"
    assert results[0].destination.name == ("20250809_194948.618_Google_Pixel-6_1.mp4")
    assert existing.read_bytes() == b"already here"


def test_video_uppercase_suffix_is_normalized(source: Path, tmp_path: Path, make_video):
    make_video("incoming/PXL_20250809_194948618.MP4")

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "moved"
    assert results[0].destination.suffix == ".mp4"


def test_video_make_model_sanitization(source: Path, tmp_path: Path, make_video):
    make_video(
        "incoming/PXL_20250809_194948618.TS.mp4",
        android_make="Google  Inc.",
        android_model="Pixel  6--Pro",
    )

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "moved"
    assert results[0].destination.name == (
        "20250809_194948.618_Google-Inc._Pixel-6-Pro.mp4"
    )


def test_apple_keys_metadata(source: Path, tmp_path: Path, make_video):
    make_video(
        "incoming/IMG_1234.MOV",
        android_make=None,
        android_model=None,
        apple_make="Apple",
        apple_model="iPhone 15",
    )

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "moved"
    assert results[0].destination.name == "20250809_195121_Apple_iPhone-15.mov"


def test_apple_udta_metadata_fallback(source: Path, tmp_path: Path, make_video):
    make_video(
        "incoming/IMG_1234.MOV",
        android_make=None,
        android_model=None,
        udta_make="Apple",
        udta_model="iPhone 14",
    )

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "moved"
    assert results[0].destination.name == "20250809_195121_Apple_iPhone-14.mov"


@pytest.mark.parametrize(
    ("value", "expected", "subsec"),
    [
        ("2025-08-09T19:51:21", datetime(2025, 8, 9, 19, 51, 21), None),
        ("2025-08-09T19:51:21.250+0200", datetime(2025, 8, 9, 19, 51, 21), "250"),
        ("2025-08-09T19:51:21Z", datetime(2025, 8, 9, 19, 51, 21), None),
        ("2025-08-09T19:51:21+02:00", datetime(2025, 8, 9, 19, 51, 21), None),
    ],
)
def test_apple_creation_date_iso_formats(
    tmp_path: Path, make_video, value, expected, subsec
):
    src = make_video(
        "incoming/IMG_1234.MOV",
        apple_creation_date=value,
        creation_time=datetime(2024, 1, 1),
    )

    metadata = read_metadata(src)

    assert metadata.datetime_original == expected
    assert metadata.subsec_time_original == subsec


def test_invalid_apple_creation_date_falls_back_to_movie_header(
    tmp_path: Path, make_video
):
    src = make_video(
        "incoming/IMG_1234.MOV",
        apple_creation_date="not-a-date",
        creation_time=datetime(2024, 1, 2, 3, 4, 5),
    )

    metadata = read_metadata(src)

    assert metadata.datetime_original == datetime(2024, 1, 2, 3, 4, 5)


def test_android_metadata_takes_precedence_over_apple(
    source: Path, tmp_path: Path, make_video
):
    make_video(
        "incoming/IMG_1234.MOV",
        android_make="Google",
        android_model="Pixel 6",
        apple_make="Apple",
        apple_model="iPhone 15",
        apple_creation_date="2025-08-09T19:51:21+0200",
        creation_time=datetime(2024, 1, 1),
    )

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "moved"
    assert results[0].destination.name == "20250809_195121_Google_Pixel-6.mov"


def test_apple_creation_date_is_used_before_movie_header(
    source: Path, tmp_path: Path, make_video
):
    make_video(
        "incoming/IMG_1234.MOV",
        android_make=None,
        android_model=None,
        apple_make="Apple",
        apple_model="iPhone 15",
        apple_creation_date="2025-08-09T19:51:21+0200",
        creation_time=datetime(2024, 1, 1),
    )

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "moved"
    assert results[0].destination.name == "20250809_195121_Apple_iPhone-15.mov"


def test_filename_timestamp_wins_over_apple_creation_date(
    source: Path, tmp_path: Path, make_video
):
    make_video(
        "incoming/PXL_20250809_194948618.TS.mp4",
        apple_creation_date="2020-01-02T03:04:05Z",
        creation_time=datetime(2021, 2, 3, 4, 5, 6),
    )

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "moved"
    assert results[0].destination.name == ("20250809_194948.618_Google_Pixel-6.mp4")


def test_apple_creation_date_with_fraction_and_offset_is_named(
    source: Path, tmp_path: Path, make_video
):
    make_video(
        "incoming/IMG_1234.MOV",
        android_make=None,
        android_model=None,
        apple_make="Apple",
        apple_model="iPhone 15",
        apple_creation_date="2025-08-09T19:51:21.250+0200",
        creation_time=datetime(2024, 1, 1),
    )

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "moved"
    assert results[0].destination.name == "20250809_195121.250_Apple_iPhone-15.mov"


def test_legacy_day_tag_is_used_before_movie_header(
    source: Path, tmp_path: Path, make_video
):
    make_video(
        "incoming/IMG_1234.MOV",
        android_make=None,
        android_model=None,
        apple_make="Apple",
        apple_model="iPhone 14",
        udta_day="2025-08-09T19:51:21+0200",
        creation_time=datetime(2024, 1, 1),
    )

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "moved"
    assert results[0].destination.name == "20250809_195121_Apple_iPhone-14.mov"


def test_image_with_timestamp_filename_still_uses_exif(
    source: Path, tmp_path: Path, make_image
):
    make_image(
        "incoming/PXL_20250809_194948618.jpg",
        datetime_original="2024:07:15 12:34:56",
    )

    results = import_images(source, tmp_path / "archive")

    assert results[0].status == "moved"
    assert results[0].destination.name == "20240715_123456_Canon_EOS-5D.jpg"


def test_video_metadata_fixture_has_video_track(tmp_path: Path, make_video):
    src = make_video("incoming/clip.mp4")

    metadata = read_metadata(src)

    assert metadata.make == "Google"
    assert metadata.model == "Pixel 6"
    assert metadata.file_type_extension == "mp4"


def test_video_fixture_writes_apple_creation_date(tmp_path: Path, make_video):
    src = make_video(
        "incoming/IMG_1234.MOV",
        apple_creation_date="2025-08-09T19:51:21+0200",
        udta_day="2025-08-09T19:51:21+0200",
    )

    data = src.read_bytes()

    assert b"com.apple.quicktime.creationdate" in data
    assert b"\xa9day" in data

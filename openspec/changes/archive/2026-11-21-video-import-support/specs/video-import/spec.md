# Spec Delta

## Purpose

Defines how camera videos in ISO base media containers are recognized, read for
metadata, timestamped, named, and moved into the date-based archive alongside
photos.

## ADDED Requirements

### Requirement: ISO-BMFF video recognition

The importer SHALL recognize MP4, MOV, M4V, and 3GP files by inspecting the
ISO base media file format structure, not merely the filename suffix. Files in
other video containers SHALL be skipped as unsupported.

#### Scenario: Top Shot MP4 is recognized

- **WHEN** the source contains `PXL_20250809_194948618.TS.mp4` with an ISO-BMFF
  `ftyp` box
- **THEN** the importer treats it as a supported video rather than a
  non-image file

#### Scenario: Unsupported container is skipped

- **WHEN** the source contains a file such as `clip.mkv`, `clip.avi`, or
  `clip.webm`
- **THEN** the importer skips it with an unsupported-video reason and leaves
  it in place

#### Scenario: Suffix alone is not trusted

- **WHEN** a file with an `.mp4` suffix does not contain a valid ISO-BMFF
  structure
- **THEN** the importer skips it instead of importing it

### Requirement: Android video metadata

The importer SHALL read the make and model of Android videos from the
`com.android.manufacturer` and `com.android.model` metadata keys.

#### Scenario: Pixel video metadata

- **WHEN** a video contains `com.android.manufacturer` = `Google` and
  `com.android.model` = `Pixel 6`
- **THEN** the importer uses `Google` as the make and `Pixel 6` as the model

### Requirement: Apple video metadata

When Android metadata keys are absent, the importer SHALL read make and model
from Apple QuickTime metadata, including
`com.apple.quicktime.make`/`com.apple.quicktime.model` and the equivalent
`mak`/`mod` user-data tags.

#### Scenario: Apple MOV metadata

- **WHEN** a MOV file provides Apple QuickTime make and model metadata
- **THEN** the importer uses those values for the archive name

### Requirement: Video timestamp selection

The importer SHALL use a valid `YYYYMMDD_HHMMSS[mmm]` segment from the filename
as the video timestamp when one is present. Otherwise it SHALL use the `mvhd`
creation time. The `mvhd` value SHALL be treated as wall-clock time without
timezone conversion.

#### Scenario: Filename timestamp wins over movie header

- **WHEN** `PXL_20250809_194948618.TS.mp4` also reports an `mvhd` creation time
  of 2025-08-09 19:51:21
- **THEN** the importer uses 2025-08-09 19:49:48.618 from the filename

#### Scenario: Movie header fallback

- **WHEN** a video named `IMG_1234.MOV` has no timestamp segment in its
  filename and reports an `mvhd` creation time
- **THEN** the importer uses that creation time and emits no subseconds

#### Scenario: Invalid filename timestamp is ignored

- **WHEN** a filename contains a date or time segment that is not a valid
  calendar date or clock time
- **THEN** the importer ignores that segment and falls back to `mvhd`

### Requirement: Video archive naming

Videos SHALL be renamed to
`YYYYMMDD_HHMMSS[.mmm]_Make_Model.ext` and placed under `<destination>/<year>/<month>/`.
The extension SHALL be the lowercased file suffix. Google Photos `.TS` Top
Shot markers SHALL NOT be carried into the archive name. Spaces in make or
model SHALL collapse to `-`, and collisions SHALL use `_1`, `_2`, ... like
photos.

#### Scenario: Pixel video archive name

- **WHEN** `PXL_20250809_194948618.TS.mp4` with make `Google` and model
  `Pixel 6` is imported into `archive`
- **THEN** it is moved to
  `archive/2025/08/20250809_194948.618_Google_Pixel-6.mp4`

#### Scenario: Uppercase suffix is normalized

- **WHEN** a supported video has the suffix `.MP4`
- **THEN** the archive name ends in `.mp4`

#### Scenario: Video collision numbering

- **WHEN** the computed video destination already exists
- **THEN** the importer adds `_1` before the extension, then `_2`, and so on

### Requirement: Unusable videos are skipped

The importer SHALL skip videos that lack usable make, model, or timestamp
metadata, leave their bytes untouched, and report the reason.

#### Scenario: Missing video make or model

- **WHEN** a supported video has no Android or Apple make/model metadata
- **THEN** the importer skips it and reports which metadata is missing

#### Scenario: Missing video timestamp

- **WHEN** a supported video has neither a valid filename timestamp nor an
  `mvhd` creation time
- **THEN** the importer skips it and reports the missing timestamp

### Requirement: Video bytes and timestamps are preserved

Importing a video SHALL move the original bytes without re-encoding and SHALL
preserve its file modification time.

#### Scenario: Video move preserves data

- **WHEN** a supported video is imported
- **THEN** the destination has the same bytes and modification time as the
  source

### Requirement: Dry-run reports video moves

A dry run SHALL report the computed video destination without creating
directories or moving the file.

#### Scenario: Video dry run

- **WHEN** a supported video is imported with dry-run enabled
- **THEN** the result is `would_move`, the destination is reported, and the
  source remains in place

### Requirement: Image imports are unchanged

The importer SHALL continue to use EXIF metadata for images and SHALL NOT
change photo selection or naming when a photo filename also contains a
timestamp segment.

#### Scenario: JPEG still uses EXIF

- **WHEN** a JPEG named `PXL_20250809_194948618.jpg` contains EXIF
  `DateTimeOriginal`
- **THEN** the importer uses the EXIF timestamp and the existing photo naming
  rules

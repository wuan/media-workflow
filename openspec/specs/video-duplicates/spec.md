# video-duplicates Specification

## Purpose

Defines how duplicate detection and cleanup handle video copies created by the
archive naming scheme, while keeping perceptual matching limited to photos.

## Requirements

### Requirement: Video duplicate candidates

The duplicate finder SHALL treat files with the same base name and the same
supported video extension as copy candidates when they match the `_N` copy
numbering used by the importer. Supported video extensions are `.mp4`, `.mov`,
`.m4v`, and `.3gp`.

#### Scenario: Copy-numbered video is a candidate

- **WHEN** a directory contains `clip.mp4` and `clip_1.mp4`
- **THEN** both are considered candidates for duplicate comparison

#### Scenario: Related prefix is not a candidate

- **WHEN** a directory contains `clip.mp4` and `clip_extra.mp4`
- **THEN** `clip_extra.mp4` is not treated as a copy of `clip.mp4`

#### Scenario: Different video extensions are not copies

- **WHEN** a directory contains `clip.mp4` and `clip_1.mov`
- **THEN** the finder does not treat them as a copy pair

### Requirement: Exact-hash video duplicates

The duplicate finder SHALL identify video candidates with identical SHA-256
content as duplicates and SHALL keep the same survivor ordering used for
photos.

#### Scenario: Identical video copies

- **WHEN** `clip.mp4` and `clip_1.mp4` have identical bytes
- **THEN** the copy-numbered file is reported as a duplicate of the original

### Requirement: Video duplicate removal and trash

When changes are applied, video duplicates SHALL be deleted or moved into the
`.dtrash` tree exactly like photo duplicates, preserving the mirrored directory
layout when `--trash` is used.

#### Scenario: Apply deletes a video duplicate

- **WHEN** duplicate video detection runs with `--apply`
- **THEN** the reported duplicate video is removed

#### Scenario: Trash preserves video location

- **WHEN** duplicate video detection runs with `--apply --trash`
- **THEN** the duplicate video is moved into `.dtrash` under the mirrored
  relative directory

### Requirement: Fuzzy matching stays photo-only

The duplicate finder SHALL NOT apply perceptual hashing or pixel comparison to
video files, and SHALL NOT emit image-readability warnings for video candidates
during fuzzy runs. Exact-hash video detection SHALL still work when `--fuzzy`
is enabled.

#### Scenario: Fuzzy run ignores video pixels

- **WHEN** duplicate detection runs with `--fuzzy` over video candidates
- **THEN** the finder may still remove exact-hash duplicates but does not
  attempt a perceptual comparison or warn that the video is unreadable

### Requirement: Photo duplicate behaviour is unchanged

Existing JPEG duplicate detection, copy-number matching, fuzzy scoring, and
extended-XMP veto behaviour SHALL continue to apply to photos.

#### Scenario: Existing JPEG duplicate still handled

- **WHEN** a directory contains `beach.jpg` and `beach_1.jpg` with identical
  bytes
- **THEN** the JPEG duplicate is still detected and reported

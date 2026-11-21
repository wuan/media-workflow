# Spec Delta

## MODIFIED Requirements

### Requirement: Apple video metadata

When Android metadata keys are absent, the importer SHALL read make and model
from Apple QuickTime metadata, including
`com.apple.quicktime.make`/`com.apple.quicktime.model` and the equivalent
`mak`/`mod` user-data tags.

#### Scenario: Apple MOV metadata

- **WHEN** a MOV file provides Apple QuickTime make and model metadata
- **THEN** the importer uses those values for the archive name

#### Scenario: Android metadata takes precedence

- **WHEN** a video provides both Android and Apple make/model metadata
- **THEN** the importer uses the Android make and model values

#### Scenario: Apple only metadata is sufficient

- **WHEN** a video provides Apple QuickTime make and model metadata but no
  Android metadata
- **THEN** the importer imports the video instead of reporting missing make or
  model

### Requirement: Video timestamp selection

The importer SHALL use a valid `YYYYMMDD_HHMMSS[mmm]` segment from the filename
as the video timestamp when one is present. Otherwise it SHALL use the Apple
`com.apple.quicktime.creationdate` metadata key, then the legacy `©day`
user-data tag, then the `mvhd` creation time. Apple dates SHALL accept ISO 8601
dates with optional UTC offsets and fractional seconds. All metadata and
`mvhd` values SHALL be treated as wall-clock time without timezone conversion.

#### Scenario: Filename timestamp wins over movie header

- **WHEN** `PXL_20250809_194948618.TS.mp4` reports an Apple creation date of
  2025-08-09 19:51:21 and an `mvhd` creation time of 2025-08-09 19:52:00
- **THEN** the importer uses 2025-08-09 19:49:48.618 from the filename

#### Scenario: Apple creation date wins over movie header

- **WHEN** a video named `IMG_1234.MOV` has no timestamp segment in its
  filename and reports an Apple creation date of 2025-08-09 19:51:21 plus a
  different `mvhd` creation time
- **THEN** the importer uses the Apple creation date and emits no subseconds

#### Scenario: Apple date with UTC offset and fractional seconds

- **WHEN** a video reports `com.apple.quicktime.creationdate` as
  `2025-08-09T19:51:21.250+0200`
- **THEN** the importer uses 2025-08-09 19:51:21.250 as wall-clock time

#### Scenario: Legacy day tag fallback

- **WHEN** a video has no `com.apple.quicktime.creationdate` key but its
  `©day` user-data tag reports a valid creation date
- **THEN** the importer uses that date before falling back to `mvhd`

#### Scenario: Invalid Apple date falls through

- **WHEN** an Apple creation date is present but cannot be parsed as ISO 8601
- **THEN** the importer ignores it and uses the `mvhd` creation time

#### Scenario: Movie header fallback

- **WHEN** a video named `IMG_1234.MOV` has no timestamp segment in its
  filename and no Apple creation date, but reports an `mvhd` creation time
- **THEN** the importer uses that creation time and emits no subseconds

#### Scenario: Invalid filename timestamp is ignored

- **WHEN** a filename contains a date or time segment that is not a valid
  calendar date or clock time
- **THEN** the importer ignores that segment and falls back to Apple metadata
  or `mvhd`

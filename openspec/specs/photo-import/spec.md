# photo-import Specification

## Purpose

Defines how still photos provide the metadata needed for archive import and what
happens when make or model metadata is unavailable.

## Requirements

### Requirement: Photo make/model fallback

A photo SHALL be imported when its EXIF provides a usable `DateTimeOriginal`,
even if `Make` or `Model` is absent. Missing, empty, or whitespace-only values
SHALL be replaced with `unknown` for that component independently, and the
fallback SHALL be sanitized like any other make/model value when the archive
name is built.

#### Scenario: Missing make uses unknown

- **WHEN** a JPEG has `Model` `EOS 5D` and a valid `DateTimeOriginal`, but no
  `Make` tag
- **THEN** the archive name contains `unknown_EOS-5D`

#### Scenario: Missing model uses unknown

- **WHEN** a JPEG has `Make` `Canon` and a valid `DateTimeOriginal`, but no
  `Model` tag
- **THEN** the archive name contains `Canon_unknown`

#### Scenario: Both make and model are missing

- **WHEN** a JPEG has a valid `DateTimeOriginal` but neither `Make` nor `Model`
- **THEN** the archive name contains `unknown_unknown` and the photo is imported

#### Scenario: Blank make or model is treated as missing

- **WHEN** a JPEG has an empty or whitespace-only `Make` or `Model` value
- **THEN** the corresponding archive-name component is `unknown`

#### Scenario: Missing timestamp still skips the photo

- **WHEN** a photo has no usable `DateTimeOriginal` even though make or model
  fallbacks could be applied
- **THEN** the importer skips it and reports the missing timestamp rather than
  importing it

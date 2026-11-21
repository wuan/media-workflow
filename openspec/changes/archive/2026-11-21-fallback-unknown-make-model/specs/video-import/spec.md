# Spec Delta

## MODIFIED Requirements

### Requirement: Unusable videos are skipped

The importer SHALL skip videos that lack usable timestamp metadata, leave their
bytes untouched, and report the reason. Videos missing make or model SHALL NOT
be skipped; missing, empty, or whitespace-only make/model values SHALL be
replaced with `unknown` for that component independently.

#### Scenario: Missing video make or model

- **WHEN** a supported video has no Android or Apple make/model metadata
- **THEN** the importer imports it with `unknown` archive-name components
  instead of skipping it

#### Scenario: Missing video make only

- **WHEN** a supported video provides a model but no make
- **THEN** the archive name uses `unknown` as the make component

#### Scenario: Missing video timestamp

- **WHEN** a supported video has neither a valid filename timestamp nor an
  `mvhd` creation time
- **THEN** the importer skips it and reports the missing timestamp

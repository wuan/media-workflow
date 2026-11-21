# Design

## Context

See `proposal.md` for motivation and `specs/video-import/spec.md` for the
required behavior. The importer already walks ISO-BMFF `moov/meta/keys` and
`ilst` boxes, reads Android/Apple make and model keys in
`_apply_metadata_keys`, and parses `mvhd` in `_parse_mvhd`. The only missing
source is an Apple creation date.

## Goals / Non-Goals

**Goals:**

- Add Apple creation-date metadata without changing the existing filename
  and `mvhd` fallback behavior for videos that lack it.
- Keep parsing self-contained in the existing ISO-BMFF reader; no new
  dependency or external tool.
- Make precedence explicit and testable.

**Non-Goals:**

- Reading EXIF or XMP timestamps from photos; photo behavior is unchanged.
- Timezone conversion or UTC normalization.
- Editing or rewriting video metadata; the original bytes remain untouched.
- Changes to archive layout, naming collisions, or duplicate detection.

## Decisions

### Read the Apple key in the metadata-key loop

Add `com.apple.quicktime.creationdate` handling to `_apply_metadata_keys`,
next to the Android and Apple make/model cases. This keeps all `mdta`/`ilst`
keys in one place and mirrors how the Android keys are applied. Parse the value
with a dedicated ISO 8601 helper rather than `datetime.fromisoformat`, because
the project supports Python 3.10 and Apple emits offsets such as `+0200` and
`Z`.

### Keep precedence explicit with separate fields

`_VideoInfo` stores the `mvhd` time, the Apple QuickTime metadata time, and the
legacy `©day` user-data time in separate fields. `_read_video_metadata` selects:

1. a valid filename timestamp;
2. `com.apple.quicktime.creationdate`;
3. `©day`;
4. `mvhd`.

Separate fields avoid parse-order dependence: `meta` and `udta` are walked in
file order, and assigning one shared `creation_time` would let a later `©day`
tag overwrite a valid QuickTime key.

Alternative considered: assign the Apple value directly to `_VideoInfo.
creation_time` and let `©day` fill only when empty. Rejected because `mvhd` is
usually parsed first, so `©day` would never apply.

### Parse Apple dates as wall-clock values

The helper accepts `YYYY-MM-DDTHH:MM:SS`, optional fractional seconds, and an
optional numeric UTC offset (`+HHMM`, `+HH:MM`, `Z`). It discards the offset,
matching the existing `mvhd` wall-clock semantics and avoiding a timezone
database dependency. Fractional digits are carried into the filename as the
subsecond suffix, consistent with filename timestamps.

Alternative considered: normalize to UTC. Rejected because it would change
archive months for videos imported near midnight relative to the camera's
local time and would diverge from current `mvhd` behavior.

### Make/model fallback stays Android-first

Android keys continue to assign make/model unconditionally; Apple keys fill only
missing values. This is already the implementation behavior and is now captured
in the `Apple video metadata` requirement, including coexistence scenarios.

## Risks / Trade-offs

- [Apple offset discarded] → Documented as wall-clock behavior; matches `mvhd`
  and the existing archive convention.
- [Malformed Apple date] → Treat as absent and fall through to `©day`/`mvhd`;
  never fail the import because of one bad metadata value.
- [New fixture surface] → Extend the existing synthetic ISO-BMFF fixture rather
  than using real media, keeping tests hermetic.
- [`©day` is legacy] → Use it only as a fallback after the modern QuickTime key.

## Migration Plan

No migration is needed. Existing videos without Apple creation-date metadata
keep their current selection. Rollback is a code revert; no stored data format
or CLI option changes.

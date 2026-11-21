# Design

## Context

See `proposal.md` for motivation and `specs/` for the behavior contract. The
current importer opens every source file with Pillow; anything Pillow cannot
identify becomes `skipped: not a supported image`. The duplicate finder
matches only `.jpg`/`.jpeg` candidate names, and fuzzy matching relies on
Pillow image decoding. The project depends only on Pillow and its import tests
deliberately avoid real media and `exiftool`.

The reference file `PXL_20250809_194948618.TS.mp4` is a useful constraint:
its `moov` is at the end of a 229 MB file, and its metadata is spread across
`mvhd`, `meta/keys/ilst`, and `udta`.

## Goals / Non-Goals

**Goals:**

- Read video metadata with no new runtime dependency and no external tool.
- Keep the existing import, naming, collision, dry-run, and status machinery.
- Keep photo behavior and the existing public API unchanged.
- Make video behavior testable with a synthetic ISO-BMFF fixture.

**Non-Goals:**

- Decoding video frames for perceptual duplicate matching.
- Rewriting QuickTime dates in `fix-times`.
- Supporting MKV, AVI, WebM, or raw MPEG-TS containers.
- Preserving the Google Photos `.TS` marker in archive names.

## Decisions

### Content sniffing with a suffix gate

Dispatch to the video reader only for `.mp4`, `.mov`, `.m4v`, and `.3gp`
suffixes. Within that set, validate the ISO-BMFF structure instead of trusting
the suffix: require an `ftyp` box and a `moov` track whose `hdlr` handler type
is `vide`. A `.mp4`-suffixed file that fails validation is skipped as an
unsupported video.

Alternatives considered:

- Sniff `ftyp` for every file: HEIC images also use ISO-BMFF boxes, so this
  would misclassify images.
- Trust the suffix alone: would import malformed or mislabelled files.
- Detect by video track alone: audio-only `.m4a` files and images would need a
  second classification pass.

### Pure-Python ISO-BMFF reader

Implement a small seek-based box reader in the importer. It walks box headers,
validates sizes against the file length, and reads only the boxes it needs.
Never read the whole file into memory.

Boxes used:

```text
ftyp                     container confirmation
moov/mvhd                creation_time (seconds since 1904-01-01)
moov/trak/mdia/hdlr      video-track confirmation
moov/meta/keys           Android metadata key names
moov/meta/ilst           Android metadata values
moov/udta                Apple make/model and GPS
```

Alternatives considered:

- `exiftool`: conflicts with the import-test constraint and adds an external
  runtime requirement.
- `mutagen`: pure Python, but does not expose Android `keys`/`ilst` entries
  cleanly and does not provide `mvhd` creation time.
- `pymediainfo`: requires a system library.
- `av` / `ffprobe`: heavy dependency for a metadata-only need.

### Android metadata mapping

Parse the `keys` box as a list of `mdta` key names, then resolve `ilst` entries
by their 1-based index. Read `com.android.manufacturer` and
`com.android.model` from UTF-8 `data` values. Ignore unknown key indices and
malformed values rather than failing the whole import.

### Apple metadata fallback

If Android keys are absent, read
`com.apple.quicktime.make`/`com.apple.quicktime.model` from the same
keys/`ilst` structure, then fall back to the legacy `udta` tags with atom names
`mak` and `mod` (stored after the copyright byte). Make/model precedence is
Android, Apple keys, Apple `udta`.

### Filename timestamp precedence

Apply a validated regex to the path stem:

```text
(?<!\d)(\d{8})_(\d{6})(\d{3})?(?!\d)
```

Parse the date with `datetime` and reject impossible calendar dates or clock
times. If a valid match exists, use it and append the optional milliseconds as
the subsecond component. Otherwise fall back to `mvhd`.

This deliberately avoids deriving a start time by subtracting duration from
`mvhd`: the relationship is device-dependent.

### `mvhd` policy

Read `mvhd` version 0 and version 1 layouts. Convert seconds since
1904-01-01 into a naive datetime and treat it as wall-clock time, with no
timezone conversion. This matches ExifTool's default display and avoids
guessing a camera's timezone. Filename timestamps are preferred, so the
ambiguous `mvhd` path is a fallback only.

### Naming and extension

Reuse `build_filename` and `build_relative_path` so videos share the photo
scheme. Set `file_type_extension` to the lowercased source suffix. The `.TS`
marker disappears naturally because only the validated date/time segment and
make/model feed the archive name.

### Keep the public API stable

Continue exporting `ExifMetadata`, `MetadataError`, and `NotAnImageError` from
the package. The dataclass name stays for compatibility even though it now
holds video metadata too. Add a dedicated unsupported-video exception
internally and catch it in the import loop alongside the existing image errors,
so existing callers and result statuses do not change.

### Duplicate candidate extension

Extend the existing copy-number pattern from `jpe?g` to
`jpe?g|mp4|mov|m4v|3gp`. Video pairs still require the same base and extension.
Exact SHA-256 comparison is sufficient; no video-specific survivor ordering is
needed because the existing largest-file-first ordering already applies.

Guard perceptual matching by extension: compute `dhash` only for image
suffixes. Video candidates then keep exact-hash detection under `--fuzzy`
without Pillow warnings or pixel comparisons.

### Synthetic media fixtures

Add a `make_video` test fixture that writes a minimal ISO-BMFF file with
`ftyp`, `mvhd`, a video `trak`, and optional Android or Apple metadata boxes.
Tests use that fixture for both importer and duplicate behavior, preserving the
project rule against real photos and `exiftool`.

## Risks / Trade-offs

- **`moov` at the end of large files** -> Use seek-based box traversal and
  bounds checks; never load the full file.
- **Malformed box sizes** -> Treat as an unsupported video and skip; do not
  raise an unhandled parser error.
- **Filename regex false positives** -> Validate real calendar/clock values and
  require digit boundaries.
- **QuickTime timezone ambiguity** -> Prefer filename timestamps; document that
  `mvhd` fallback is wall-clock with no conversion.
- **Apple metadata variants** -> Check keys and legacy `udta` tags in order.
- **Dropping `.TS` loses the Top Shot marker** -> Accepted for archive-name
  consistency; can be revisited as a separate change.
- **Video fuzzy matching is unavailable** -> Exact-hash dedupe still works;
  perceptual matching stays photo-only until a frame decoder is justified.

## Migration Plan

The change is additive: existing archives and photo imports are unaffected.
Videos that were previously skipped will now move, so the first run should be
done with `--dry-run` to review destinations. Rollback is a code revert; no
on-disk format or schema migration is involved.

## Open Questions

None blocking implementation. Preserving `.TS` and video date shifting are
deferred to separate changes.

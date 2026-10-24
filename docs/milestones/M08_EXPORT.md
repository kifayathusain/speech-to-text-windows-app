# M08 — High-Quality Export System

Status: DONE. The [tracker](MILESTONE_TRACKER.md) is the source of truth.

## Objective

All supported formats produce playable files with correct metadata and no unexpected truncation.

## Scope

Implement only the tasks below, preserving the existing workflows. Follow the
[master plan](MASTER_PLAN.md) and [coding standards](../CODING_STANDARDS.md).

## Dependencies

M07 must pass its completion gate before implementation starts.

## Tasks

- Refactor FFmpeg processing.
- Support WAV, MP3, and M4A.
- Add optional normalization.
- Validate exported media.
- Improve error handling.

## Implementation constraints

Preserve Tkinter, Edge TTS, CLI defaults, and FFmpeg separation. No unnecessary
application rewrite, mandatory paid/cloud API, GPU dependency, or automatic
commit/push. Keep Kokoro-82M the natural-quality CPU target and Piper the
lightweight offline alternative without changing the milestone sequence.

## Acceptance criteria

All supported formats produce playable files with correct metadata and no unexpected truncation.

Pass the [shared coding standards gate](MASTER_PLAN.md#shared-compliance-gate)
and record exact evidence before DONE. Missing required validation blocks DONE.

## Test plan

Run focused unit and integration tests for the listed tasks, failure/cancellation/cleanup paths, and the complete regression suite. Use real assets/executables for relevant acceptance criteria; record manual Windows or listening checks separately.

## Expected deliverables

Implementation and behavior tests within this milestone's scope, updated
architecture/setup documentation where needed, and a completed tracker evidence
entry. No generated model/audio binaries in Git.

## Risks

Codec/sample-rate mismatch, lossy intermediates, invalid metadata, unsafe overwrite, and leaked subprocesses.

## Completion checklist

- [x] Tasks and acceptance criteria verified.
- [x] Relevant Ruff lint and formatting checks pass for changed Python files.
- [x] Existing and changed-behavior tests pass, including applicable errors,
      cancellation, and cleanup.
- [x] Required real-model/FFmpeg/Windows checks are recorded where applicable.
- [x] Manual readability and architecture review passes.
- [x] Pre-existing violations and remaining limitations are recorded separately.
- [x] Documentation and tracker are updated with reproducible evidence.

## Validation evidence

2026-10-25: Gate passed after M07.

Implemented typed export settings and actual FFprobe metadata validation; PCM WAV,
MP3 and M4A/AAC; common lossless rate/channel preparation; optional two-pass
normalization; format/bitrate/rate/channel controls; explicit overwrite choice;
non-overwriting atomic commit; and complete decoder/duration checks. Compatible
native MP3 is copied without re-encoding when no change is requested. Other work
uses disk-backed PCM intermediates and encodes only the final lossy format.

Added a reusable hidden-window child-process runner with bounded timeouts,
cooperative cancellation, terminate/kill fallback, and reaping/pipe cleanup.
Generalized background-work cleanup for inference, decoding, and exports;
repeated async task cancellation still waits for cleanup. UI stages distinguish
preparation/normalization/export/validation and remain responsive. Existing CLI
and service calls without advanced settings preserve their compatibility path.
See [export setup](../setup/AUDIO_EXPORTS.md).

Validation environment: checksum-verified Gyan FFmpeg/FFprobe 9.0.2 toolset in
ignored workspace storage, downloaded from the binary provider linked by the
[official FFmpeg download page](https://ffmpeg.org/download.html). Archive SHA-256:
`60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba`.
No toolset/model binaries were committed or automatically bundled.

```powershell
$env:PATH = "$(Resolve-Path .venv/ffmpeg-toolset);$env:PATH"
$env:TTS_EXPORT_TESTS = '1'
$env:TTS_FFMPEG_TESTS = '1'
$env:TTS_PLAYBACK_TESTS = '1'
python -m pytest -q --basetemp=.venv/m08-gate -o cache_dir=.venv/m08-cache --tb=short
```

Full suite: **198 passed, eight opt-in cases skipped in 6.52s**. Real export tests
cover all codecs, mixed native sample/channel layouts, Unicode/apostrophe paths,
normalization without accidental output upsampling, native MP3 copy, valid Auto
bitrate, incompatible bitrate/rate rejection, explicit overwrite, a late-file
creation race, failure preservation, and post-commit cleanup reporting. Actual
child tests verify nonzero-exit diagnostics, timeout/cancellation reaping, and
repeated task cancellation. Processed-job cancellation preserves prior media and
records CANCELLED metadata.

Real Tkinter/Piper M4A/WAV export/overwrite acceptance: **one passed in 22.03s**,
including event-loop heartbeat progress during generation/export, refusal of an
unapproved overwrite, acceptance of explicit replacement, and session cleanup.
A separate signed-Python-3.13 Kokoro run exercised normalized service M4A and
normalized WAV/MP3 exports from actual native speech. All retained 24 kHz mono:
PCM WAV 8.063292s, MP3 8.063292s at 160 kbps, M4A/AAC 8.10s. Codec/container and
full decode validation pass; [raw media metadata](../performance/M08_MEDIA_VALIDATION.json)
is retained without generated audio/model binaries in Git.

All 21 relevant Python files pass Ruff lint/format and manual readability,
responsibility, typed configuration, subprocess, overwrite, cancellation, and
cleanup review. Remaining unrelated baseline: two import-order lint findings
(`main.py`, `tests/test_parser.py`) and five formatting differences (`gen_audio.py`,
`main.py`, `tests/test_audio_combiner.py`, `tests/test_parser.py`,
`tests/test_tts_engine.py`). No unrelated formatting was applied.

Acceptance: supported formats are correctly identified, decode fully, retain
expected duration/selected metadata, and preserve valid prior audio on controlled
failure/cancellation. Human join acceptance remains the recorded M06 review;
no new naturalness or fidelity claim is made. Next: M09 measured performance.

# M07 — Voice Preview and UI Improvements

Status: DONE. The [tracker](MILESTONE_TRACKER.md) is the source of truth.

## Objective

Users can preview voices and configure audio generation without UI freezes.

## Scope

Implement only the tasks below, preserving the existing workflows. Follow the
[master plan](MASTER_PLAN.md) and [coding standards](../CODING_STANDARDS.md).

## Dependencies

M06 must pass its completion gate before implementation starts.

## Tasks

- Implement provider/voice selection UI.
- Add short previews.
- Add playback controls.
- Add progress and cancellation.
- Improve desktop responsiveness.

## Implementation constraints

Preserve Tkinter, Edge TTS, CLI defaults, and FFmpeg separation. No unnecessary
application rewrite, mandatory paid/cloud API, GPU dependency, or automatic
commit/push. Keep Kokoro-82M the natural-quality CPU target and Piper the
lightweight offline alternative without changing the milestone sequence.

## Acceptance criteria

Users can preview voices and configure audio generation without UI freezes.

Pass the [shared coding standards gate](MASTER_PLAN.md#shared-compliance-gate)
and record exact evidence before DONE. Missing required validation blocks DONE.

## Test plan

Run focused unit and integration tests for the listed tasks, failure/cancellation/cleanup paths, and the complete regression suite. Use real assets/executables for relevant acceptance criteria; record manual Windows or listening checks separately.

## Expected deliverables

Implementation and behavior tests within this milestone's scope, updated
architecture/setup documentation where needed, and a completed tracker evidence
entry. No generated model/audio binaries in Git.

## Risks

Cross-thread widget access, playback conflicts, stale previews, and incomplete cancellation.

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

2026-10-24: Gate passed after M06 and its user listening acceptance.

Implemented provider/voice selection, language filtering, explicit online/offline
and runtime information, per-provider voice memory, supported speed controls,
processed-text/pauses controls, selected-text/sample previews, replay/stop,
cancellation, chunk/line progress, elapsed time, word/character counts,
Paste/Clear, and output-folder opening. Retained Tkinter, speaker naming,
editable custom Edge voice IDs, original Edge defaults, and the existing service.

New `ProviderManager` owns verified model selection and single-session lifecycle;
`PreviewService` owns bounded selected-voice/speed synthesis and an eight-entry
validated PCM cache keyed to text/settings/model identity; `WindowsAudioPlayer`
uses asynchronous native playback. Typed immutable desktop options are captured
on the main thread, and worker messages render only on the UI thread. Late
preview results after settings changes are ignored. Preview/export work is
serialized; generation stops playback. Model modification closes idle sessions
from its worker, and modal model management prevents conflicting UI operations.
Shutdown requests cancellation and waits asynchronously for cleanup/unload.

Speed now reaches all synthesis requests and job fingerprints/metadata. No local
inference runtime is imported simply to show provider choices. Missing models
and unsupported Kokoro Python profiles report actionable errors without online
fallback. See [desktop setup](../setup/DESKTOP_PREVIEW.md).

Validation:

```powershell
python -m pytest -q --basetemp=.venv/m07-gate -o cache_dir=.venv/m07-cache --tb=short
$env:TTS_PREVIEW_MODEL_ROOT = (Resolve-Path .venv/validation-models).Path
.\.venv\python313-official\python.exe -m pytest -q tests/test_preview_integration.py --basetemp=.venv/m07-preview-real -o cache_dir=.venv/m07-real-cache --tb=short
python -m pytest -q tests/test_gui_integration.py --basetemp=.venv/m07-gui-final -o cache_dir=.venv/m07-gui-cache --tb=short
```

Full suite with real FFmpeg/Windows playback enabled: **169 passed, seven opt-in
cases skipped in 1.50s**. Actual Kokoro/Piper preview/cache/session-release case:
**one passed in 14.46s** on signed Python 3.13, with Python network helpers denied.
Model assets were installed from previously upstream-verified local validation
files through the real manager; M05 separately tested actual fresh downloads.
Real Tkinter/Piper/cancellation plus Windows playback cases: **two passed in
6.03s** on Python 3.14 with optional Piper dependencies. The live event loop kept
heartbeat callbacks running during inference; playback/replay was dispatched
on the main thread. Settings invalidation, cancellation, stale-result rejection,
resource release, and model removal after shutdown were verified. Native playback
API accepted PCM and stopped; no subjective listening claim was added.

Unit cases cover provider metadata without model loads, missing-model errors,
selected-session cleanup, disabled controls, invalid speed, preview cache keys,
bounded eviction, corrupted-cache regeneration, temporary cleanup, cancellation,
non-label colons, async playback flags, and generation-vs-preview conflict guards.
All 16 relevant Python files pass Ruff lint/format and manual readability,
responsibility, type/error handling, thread-boundary, and cleanup review.
Repository baseline remains two import-order lint findings and five formatting
differences in untouched files.

Acceptance: real local preview files, playback API, responsive desktop controls,
cache invalidation, and cancellation all validate. Kokoro backend is validated on
supported signed Python 3.13; live Tkinter inference was tested using Piper on
Python 3.14. A complete packaged Kokoro desktop/clean OS is M10 scope. Optional
text-file import is not implemented; Paste/Clear preserve script editing.
Next milestone: M08 validated high-quality exports.

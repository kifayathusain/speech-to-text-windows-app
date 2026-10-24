# M06 — Text Chunking and Natural Speech Processing

Status: DONE. The [tracker](MILESTONE_TRACKER.md) is the source of truth.

## Objective

Long text generates in the correct order without missing or duplicated text, and output joins are audibly acceptable.

## Scope

Implement only the tasks below, preserving the existing workflows. Follow the
[master plan](MASTER_PLAN.md) and [coding standards](../CODING_STANDARDS.md).

## Dependencies

M05 must pass its completion gate before implementation starts.

## Tasks

- Implement sentence-aware chunking.
- Add paragraph pauses.
- Add text normalization.
- Improve long-form generation.
- Add output metadata and chunk tracking.

## Implementation constraints

Preserve Tkinter, Edge TTS, CLI defaults, and FFmpeg separation. No unnecessary
application rewrite, mandatory paid/cloud API, GPU dependency, or automatic
commit/push. Keep Kokoro-82M the natural-quality CPU target and Piper the
lightweight offline alternative without changing the milestone sequence.

## Acceptance criteria

Long text generates in the correct order without missing or duplicated text, and output joins are audibly acceptable.

Pass the [shared coding standards gate](MASTER_PLAN.md#shared-compliance-gate)
and record exact evidence before DONE. Missing required validation blocks DONE.

## Test plan

Run focused unit and integration tests for the listed tasks, failure/cancellation/cleanup paths, and the complete regression suite. Use real assets/executables for relevant acceptance criteria; record manual Windows or listening checks separately.

## Expected deliverables

Implementation and behavior tests within this milestone's scope, updated
architecture/setup documentation where needed, and a completed tracker evidence
entry. No generated model/audio binaries in Git.

## Risks

Lost punctuation, duplicated or missing text, abbreviations, long sentences, and audio join artifacts.

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

2026-10-24: Gate passed after M05, including explicit user listening acceptance.

Implemented conservative Unicode/whitespace normalization, sentence/word/long-word
chunking within provider limits, abbreviation/decimal/CJK/quote handling,
paragraph metadata, configurable sentence/paragraph PCM pauses, isolated jobs,
atomic privacy-preserving chunk/output metadata, completed-chunk retention,
and line plus chunk progress. Offline engines use the processed path; Edge
retains its original default path and can opt in explicitly. FFmpeg stays in its
adapter; native MP3 is decoded to lossless PCM only when processing requires it.
Cancellation is checked before media publication, preserving previous exports.
See [text-processing setup](../setup/TEXT_PROCESSING.md).

Changes: new `text_processing.py` and `generation.py`, parser paragraph metadata,
service routing, shared silence generation, FFmpeg decode/cancellation checks,
unit/integration coverage, and a reproducible listening-sample script. Existing
parser annotations/formatting were modernized within the changed module only.
No source text is recorded in generation metadata or ordinary diagnostics.

Validation:

```powershell
python -m pytest -q --basetemp=.venv/m06-complete -o cache_dir=.venv/m06-cache --tb=short
.\.venv\python313-official\python.exe -m pytest -q tests/test_longform_integration.py tests/test_kokoro_integration.py tests/test_piper_integration.py --basetemp=.venv/m06-real -o cache_dir=.venv/m06-real-cache --tb=short
.\.venv\python313-official\python.exe -m scripts.create_m06_listening_sample --model-dir .venv/validation-models/kokoro --output-dir .venv/acceptance/m06
```

Full suite with real FFmpeg routing enabled: **150 passed, five opt-in model/download
cases skipped in 3.29s**. Actual signed Python 3.13 long-form/Kokoro/Piper media
checks: **three passed in 67.36s**. The real long-form source exceeds 2,000
characters, generates bounded ordered requests without loss/duplication, adds
paragraph silence, tracks all chunks, and produces an MP3 whose decoded duration
matches source chunks plus pauses. Python network helpers are denied during
local inference. A separate real FFmpeg case verifies opted-in Edge MP3-to-PCM
processing using controlled native audio (no live Edge service request).

Unit cases verify exact source span partition, Unicode, dates/abbreviations,
word fallback, provider limits, exact silence frames, no leading/trailing pause,
metadata privacy/states, isolated jobs, failures/cancellation preserving existing
media, metadata cleanup, and post-commit metadata warning behavior. All 13
relevant Python files pass Ruff lint/format and manual readability/boundary/error
review. Repository-wide checks retain only two unrelated import-order lint
findings and six formatting differences in untouched files.

Human listening: the user listened to `.venv/acceptance/m06/join-review.mp3`,
a real two-voice Kokoro sample with 0.15-second sentence and 0.4-second paragraph
pauses, and explicitly answered **“The joins sound acceptable”** on 2026-10-24.
This satisfies the audible-join acceptance criterion. It is not a general voice
naturalness score or a claim that every configuration has been listened to.

Acceptance: long source order/content is preserved under actual CPU generation,
final media validates, and the required listening check passes. Automatic resume,
advanced desktop controls, full codec normalization, and aggressive subprocess
interruption remain later scope. M07 provider/preview UI may begin.

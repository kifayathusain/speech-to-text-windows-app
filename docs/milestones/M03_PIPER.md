# M03 — Piper Offline Provider

Status: DONE. The [tracker](MILESTONE_TRACKER.md) is the source of truth.

## Objective

A downloaded Piper voice produces valid audio with internet disabled.

## Scope

Implement only the tasks below, preserving the existing workflows. Follow the
[master plan](MASTER_PLAN.md) and [coding standards](../CODING_STANDARDS.md).

## Dependencies

M02 must pass its completion gate before implementation starts.

## Tasks

- Select an appropriate supported Piper implementation.
- Integrate local CPU synthesis.
- Add voice discovery.
- Implement model validation.
- Test real-model WAV generation.

## Implementation constraints

Preserve Tkinter, Edge TTS, CLI defaults, and FFmpeg separation. No unnecessary
application rewrite, mandatory paid/cloud API, GPU dependency, or automatic
commit/push. Keep Kokoro-82M the natural-quality CPU target and Piper the
lightweight offline alternative without changing the milestone sequence.

## Acceptance criteria

A downloaded Piper voice produces valid audio with internet disabled.

Pass the [shared coding standards gate](MASTER_PLAN.md#shared-compliance-gate)
and record exact evidence before DONE. Missing required validation blocks DONE.

## Test plan

Run unit failures/cancellation/cleanup tests and synthesize real WAV with a verified downloaded Piper voice while internet access is disabled. Probe/decode the output and exercise final export with real FFmpeg.

## Expected deliverables

Implementation and behavior tests within this milestone's scope, updated
architecture/setup documentation where needed, and a completed tracker evidence
entry. No generated model/audio binaries in Git.

## Risks

Python/Windows wheel compatibility, phonemizer packaging, model licensing, and offline validation.

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

2026-10-24: Gate passed after M02.

Implemented optional Piper 1.8.0 CPU inference, explicit voice descriptors and
SHA-256 asset validation, known-voice discovery without arbitrary directory
loading, lazy single-session reuse, speed control, serialized off-event-loop
inference, cooperative/task cancellation, atomic WAV output, and explicit session
release. Native WAV now passes through the existing FFmpeg adapter to correctly
encoded MP3 or PCM WAV; mismatched segment sample rates/channels fail explicitly.
The default Edge UI/CLI and its stream-copy export remain unchanged.

New files: `requirements-piper.txt`, `ttsapp/models/{__init__,assets,piper_catalog}.py`,
`ttsapp/providers/piper.py`, three test modules (`test_piper`,
`test_piper_integration`, `test_wav_export`), and [Piper setup](../setup/PIPER.md).
Updated service/audio adapter and provider format test within M03 scope.

Runtime: Python 3.14.7, Piper 1.8.0, ONNX Runtime 1.31.0 CPU, NumPy 2.5.4,
FFmpeg 7.1 supplied by isolated imageio-ffmpeg 0.6.0 validation tooling. Optional
packages and downloaded model/audio remain under ignored `.venv`; neither test
tooling nor models are bundled or added as mandatory application dependencies.
Model: pinned `en_US-lessac-low`, 63,201,294 bytes; model/config checksums and
upstream revision/license references are recorded in the setup document.
Model SHA-256 was checked against upstream LFS metadata and configuration
identity against its pinned Git blob before recording its SHA-256.

Commands (run outside sandbox restrictions):

```powershell
$env:PYTHONPATH = "$(Resolve-Path .venv/quality-tools);$(Resolve-Path .venv/offline-runtime/Lib/site-packages);$(Resolve-Path .venv/Lib/site-packages)"
$env:PATH = "$(Resolve-Path .venv/validation-bin);$env:PATH"
$env:TTS_PIPER_MODEL_DIR = (Resolve-Path .venv/validation-models/piper).Path
python -m pytest -q --basetemp=.venv/m03-final -o cache_dir=.venv/m03-cache --tb=short
```

Result: **89 passed in 9.77 seconds**, including actual inference with Python
DNS/network connection helpers blocked. The CPU-only session was loaded once
and reused for direct WAV and two-line conversation generation. Tests verified
nonzero mono 16-bit/16 kHz PCM samples, decoded the final MP3 with real FFmpeg,
and checked duration against the input segments. No OS network adapter was
disabled; the verified claim is local inference with Python network calls denied.
An upstream direct smoke measured model load at 4.39 seconds and produced 40,448
frames at 16 kHz; this is a single setup observation, not a performance promise.

After making the task-cancellation test's scheduling deterministic, the default
suite without Piper dependencies passed: **88 passed, 1 skipped in 0.58 seconds**.
The one real-model test is intentionally opt-in when assets/runtime are absent.
All 15 relevant Python files pass Ruff lint/format. Repository checks now retain
15 pre-existing lint violations and eight formatting differences in untouched
files. Manual readability, typed boundaries, errors, cleanup, and architecture
review passed. No unrelated source rewrite, commit, or push was performed.

Acceptance: real downloaded Piper assets produce valid CPU speech using local
files, with Python network calls denied, and correctly encoded final media.
No naturalness claim or human listening result is made. Cancellation waits for
native inference boundaries; mixed sample-rate normalization, M4A, model download
UI, and desktop provider switching remain later scope. Next: M04 Kokoro-82M.

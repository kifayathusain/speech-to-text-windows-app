# M04 — Kokoro Natural Voice Provider

Status: DONE. The [tracker](MILESTONE_TRACKER.md) is the source of truth.

## Objective

Real Kokoro synthesis works offline on CPU-only Windows and produces valid audio through the existing export pipeline.

## Scope

Implement only the tasks below, preserving the existing workflows. Follow the
[master plan](MASTER_PLAN.md) and [coding standards](../CODING_STANDARDS.md).

## Dependencies

M03 must pass its completion gate before implementation starts.

## Tasks

- Evaluate maintained Kokoro ONNX runtimes.
- Choose a suitable CPU-compatible implementation.
- Integrate Kokoro-82M.
- Implement voice selection and lazy model loading.
- Add quality and CPU benchmarks.

## Implementation constraints

Preserve Tkinter, Edge TTS, CLI defaults, and FFmpeg separation. No unnecessary
application rewrite, mandatory paid/cloud API, GPU dependency, or automatic
commit/push. Keep Kokoro-82M the natural-quality CPU target and Piper the
lightweight offline alternative without changing the milestone sequence.

## Acceptance criteria

Real Kokoro synthesis works offline on CPU-only Windows and produces valid audio through the existing export pipeline.

Pass the [shared coding standards gate](MASTER_PLAN.md#shared-compliance-gate)
and record exact evidence before DONE. Missing required validation blocks DONE.

## Test plan

Run real Kokoro-82M synthesis offline using CPU only; measure initialization, synthesis, generated duration, real-time factor, and memory. Probe exported output; record a separate human listening evaluation for quality claims.

## Expected deliverables

Implementation and behavior tests within this milestone's scope, updated
architecture/setup documentation where needed, and a completed tracker evidence
entry. No generated model/audio binaries in Git.

## Risks

CPU latency, memory use, ONNX compatibility, phonemizer assets, and unverified naturalness claims.

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

2026-10-24: M04 gate passed after M03's real-model gate.

Implemented `KokoroTTSProvider`, explicit unquantized model/voice descriptors,
verified SHA-256 assets, four English voice choices, lazy reusable CPU sessions,
configurable CPU threads, bounded native segments, speed controls, safe PCM
conversion, atomic WAV publication, cooperative cancellation, and explicit
session/archive release. Optional dependencies are in `requirements-kokoro.txt`;
no mandatory cloud, GPU, or PyTorch dependency. Defaults still use Edge.

Extracted shared native WAV writing and cancellable background-worker handling
for the now-two offline engines, rather than duplicating atomic output/cleanup.
Piper's existing tests and real synthesis still pass after this scoped change.
Added unit/real-model tests, optional benchmark tooling/dependency, and
[Kokoro setup](../setup/KOKORO.md). The original architecture snapshot is retained
as a historical baseline.

Environment obstacle resolved without disabling security: kokoro-onnx requires
Python 3.10–3.13. The managed Python 3.13 runtime's unsigned `_overlapped` was
blocked by Windows Application Control. Official signed Python 3.13.17 imported
asyncio/Kokoro and executed CPU synthesis successfully. Existing Python 3.14 and
the old virtual environment remain intact. Official embeddable Python was used
only for backend validation, not claimed as a complete desktop installation.

Validation commands, with FFmpeg from ignored validation tooling on PATH:

```powershell
python -m pytest -q --basetemp=.venv/m04-unit -o cache_dir=.venv/m04-cache --tb=short
$env:TTS_KOKORO_MODEL_DIR = (Resolve-Path .venv/validation-models/kokoro).Path
$env:TTS_PIPER_MODEL_DIR = (Resolve-Path .venv/validation-models/piper).Path
.\.venv\python313-official\python.exe -m pytest -q tests/test_kokoro_integration.py tests/test_piper_integration.py tests/test_kokoro.py tests/test_piper.py tests/test_audio_files.py tests/test_wav_export.py --basetemp=.venv/m04-real -o cache_dir=.venv/m04-real-cache --tb=short
.\.venv\python313-official\python.exe -m scripts.benchmark_kokoro --model-dir .venv/validation-models/kokoro --output-dir .venv/benchmarks/kokoro-m04 --cpu-threads 2
```

Default regressions: **103 passed, two opt-in real-model tests skipped in 2.48s**.
Signed Python 3.13 real-model/provider tests: **35 passed in 32.30s**, including
Kokoro/Piper CPU-only sessions with Python DNS/connection helpers blocked, valid
PCM, multiple voices/session reuse, and real FFmpeg MP3 decoding. No OS network
adapter was disabled. Actual Kokoro inference/output is verified, not mocked.
Relevant Ruff lint/format and manual readability/architecture review pass.
Repository baseline remains 15 unrelated lint findings/eight formatting differences.

[Measured quality/CPU report](../performance/M04_KOKORO.md): model verification
and load 3.31s; first completed audio 9.00s; observed RTF 1.29–1.57 at two threads;
peak process working set about 635 MiB; valid PCM levels/no measured clipping.
These results are slower than real time and are not speed guarantees. Human
listening is pending; no claim of naturalness is made from waveform validation.
No M09 optimization or M10 desktop packaging/clean-machine result is claimed.

Acceptance: real Kokoro-82M works using local assets on CPU-only Windows and
produces valid native WAV and correctly encoded final MP3 through the existing
export pipeline. Gate passed for M04; proceed to M05 model management.

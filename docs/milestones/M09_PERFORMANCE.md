# M09 — Performance Optimization

Status: DONE. The [tracker](MILESTONE_TRACKER.md) is the source of truth.

## Objective

Real benchmark results are recorded and no unacceptable regression is introduced.

## Scope

Implement only the tasks below, preserving the existing workflows. Follow the
[master plan](MASTER_PLAN.md) and [coding standards](../CODING_STANDARDS.md).

## Dependencies

M08 must pass its completion gate before implementation starts.

## Tasks

- Benchmark Kokoro, Piper, and Edge separately.
- Optimize CPU threads.
- Reduce memory usage.
- Improve caching.
- Optimize model lifecycle.
- Document measured results.

## Implementation constraints

Preserve Tkinter, Edge TTS, CLI defaults, and FFmpeg separation. No unnecessary
application rewrite, mandatory paid/cloud API, GPU dependency, or automatic
commit/push. Keep Kokoro-82M the natural-quality CPU target and Piper the
lightweight offline alternative without changing the milestone sequence.

## Acceptance criteria

Real benchmark results are recorded and no unacceptable regression is introduced.

Pass the [shared coding standards gate](MASTER_PLAN.md#shared-compliance-gate)
and record exact evidence before DONE. Missing required validation blocks DONE.

## Test plan

Run focused unit and integration tests for the listed tasks, failure/cancellation/cleanup paths, and the complete regression suite. Use real assets/executables for relevant acceptance criteria; record manual Windows or listening checks separately.

## Expected deliverables

Implementation and behavior tests within this milestone's scope, updated
architecture/setup documentation where needed, and a completed tracker evidence
entry. No generated model/audio binaries in Git.

## Risks

Unrepeatable timings, oversubscribed threads, memory regressions, and mocked performance claims.

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

Completed 2026-10-25. [Measurements and tradeoffs](../performance/M09_PERFORMANCE.md)
and [raw reports](../performance/M09_BENCHMARKS.json) cover real Kokoro, Piper,
and Edge separately. Full precision Kokoro is retained. Four CPU threads,
provider/session reuse, resident catalog styles, and per-provider arena settings
are selected from measurements; cold-start/throughput tradeoffs are explicit.

Changed files: `providers/kokoro.py`, `piper.py`, shared `onnx_sessions.py`,
`provider_manager.py`, `scripts/benchmark_providers.py`; behavior tests in
`test_kokoro.py`, `test_piper.py`, `test_piper_integration.py`,
`test_provider_manager.py`, and `test_onnx_sessions.py`. Setup/architecture and
performance documentation describe the final behavior.

Commands run from repository root:

```powershell
$env:PYTHONPATH = "$(Resolve-Path .venv/quality-tools);$(Resolve-Path .venv/Lib/site-packages)"
$env:PATH = "$(Resolve-Path .venv/ffmpeg-toolset);$env:PATH"
$env:TTS_EXPORT_TESTS = '1'
$env:TTS_FFMPEG_TESTS = '1'
$env:TTS_PLAYBACK_TESTS = '1'
python -m pytest -q --basetemp=.venv/m09-full -o cache_dir=.venv/m09-fullcache --tb=short
python -m ruff check .
python -m ruff format --check .
```

Full suite: **204 passed, eight opt-in skips**, 10.01s. The final arena default
was subsequently exercised by the actual Kokoro/preview tests below; the full
suite tests configuration independent of inference defaults.

```powershell
$env:TTS_KOKORO_MODEL_DIR = (Resolve-Path .venv/validation-models/kokoro).Path
$env:TTS_PIPER_MODEL_DIR = (Resolve-Path .venv/validation-models/piper).Path
$env:TTS_PREVIEW_MODEL_ROOT = (Resolve-Path .venv/validation-models).Path
.\.venv\python313-official\python.exe -m pytest tests/test_kokoro_integration.py tests/test_piper_integration.py tests/test_preview_integration.py tests/test_kokoro.py tests/test_piper.py tests/test_provider_manager.py tests/test_onnx_sessions.py -q --basetemp=.venv/m09-real -o cache_dir=.venv/m09-realcache --tb=short
```

**38 passed**, 39.98s. Real local tests block Python DNS/connection helpers.
Real Windows Tkinter/Piper UI/export tests under signed system Python 3.14:
`python -m pytest tests/test_gui_integration.py tests/test_gui_export_integration.py
-q --basetemp=.venv/m09-gui -o cache_dir=.venv/m09-guicache --tb=short`, using
`.venv/offline-runtime/Lib/site-packages` and `TTS_GUI_PIPER_MODEL_DIR`:
**two passed, one playback opt-in skip**, 26.47s. Playback passed in the full run.

Relevant Ruff commands use the ten changed Python paths listed above with
`ruff check` and `ruff format --check`: both pass, ten files already formatted.
Repository-wide checks retain only **two pre-existing I001 findings** in
`main.py`/`tests/test_parser.py` and **five formatting differences** in those
files plus `gen_audio.py`, `tests/test_audio_combiner.py`, and
`tests/test_tts_engine.py`. They remain untouched, with no suppressed rules.

New tests cover repeated session use, re-verification after close/prevalidation,
resident styles/archive closure and explicit CPU settings. Existing cancellation,
atomic output, errors and UI cleanup regressions pass. Manual review confirms
focused provider/audio/UI boundaries, descriptive names, type hints, explicit
control flow/errors, no compressed statements, and no unrelated formatting.
Documentation links/fences, ten milestone templates, and TOML were validated.
M10 may begin. Benchmarks are small laptop observations, not universal latency
or naturalness guarantees; see the detailed report for remaining tradeoffs.

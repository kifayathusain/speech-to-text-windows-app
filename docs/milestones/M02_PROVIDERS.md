# M02 — Provider Abstraction and Edge Migration

Status: DONE. The [tracker](MILESTONE_TRACKER.md) is the source of truth.

## Objective

Existing Edge TTS generation passes all regression tests.

## Scope

Implement only the tasks below, preserving the existing workflows. Follow the
[master plan](MASTER_PLAN.md) and [coding standards](../CODING_STANDARDS.md).

## Dependencies

M01 must pass its completion gate before implementation starts.

## Tasks

- Introduce provider registry.
- Create common synthesis requests and responses.
- Move Edge integration behind provider interface.
- Preserve current UI and output behavior.

## Implementation constraints

Preserve Tkinter, Edge TTS, CLI defaults, and FFmpeg separation. No unnecessary
application rewrite, mandatory paid/cloud API, GPU dependency, or automatic
commit/push. Keep Kokoro-82M the natural-quality CPU target and Piper the
lightweight offline alternative without changing the milestone sequence.

## Acceptance criteria

Existing Edge TTS generation passes all regression tests.

Pass the [shared coding standards gate](MASTER_PLAN.md#shared-compliance-gate)
and record exact evidence before DONE. Missing required validation blocks DONE.

## Test plan

Run registry, capability, invalid-selection, default Edge, injection, cancellation, and unchanged CLI/UI/adapter regressions with network mocked.

## Expected deliverables

Implementation and behavior tests within this milestone's scope, updated
architecture/setup documentation where needed, and a completed tracker evidence
entry. No generated model/audio binaries in Git.

## Risks

Changed defaults, accidental eager offline imports, cancellation leaks, and regressions.

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

2026-10-24: Gate passed. M01 was DONE before implementation began.

Implemented typed immutable capabilities/voice/request/result records, a
thread-safe cancellation token, provider protocol, explicit registry, and Edge
provider. The service resolves one provider per generation and validates all
requests before filesystem effects. Existing callers still select Edge by
default. Custom Edge voice IDs, script parsing, progress, default paths, CLI,
Tkinter UI, FFmpeg combination, and legacy `synthesize_line` remain supported.
No local runtime, model, GPU package, or cloud API dependency was added.

Changed Python: `ttsapp/providers/{__init__,base,registry,edge}.py`,
`ttsapp/service.py`, `ttsapp/tts_engine.py`, and `tests/test_providers.py`.
The Edge provider delegates to the existing atomic adapter. Optional tokens
cancel live network tasks and are checked before atomic publication; direct
async task cancellation propagates and cleans partial files. FFmpeg cancellation
is still outside M02 and the UI does not yet expose cancellation controls.

Commands, using the M01 process-local PYTHONPATH/system Python environment:

```powershell
python -m pytest -q --basetemp=.venv/m02-validation2 -o cache_dir=.venv/m02-cache --tb=short
python -m ruff check ttsapp/providers ttsapp/service.py ttsapp/tts_engine.py tests/test_providers.py tests/test_baseline.py
python -m ruff format --check ttsapp/providers ttsapp/service.py ttsapp/tts_engine.py tests/test_providers.py tests/test_baseline.py
python -m ruff check . --statistics
python -m ruff format --check . --output-format concise
```

Results: **70 passed in 1.05 seconds**; all eight relevant Python files pass Ruff
lint/format. An initial collection error from using pytest's reserved `request`
parameter name was corrected before this passing run. The full suite includes
all 49 M01 regressions plus 21 provider cases for registration, metadata,
validation, routing, configuration-before-side-effects, task/token cancellation,
and cleanup/preservation at the atomic publication boundary.

Manual review passed for names, type hints, explicit errors/control flow,
focused responsibilities, cancellation cleanup, and architecture boundaries.
Modernized annotations only in the changed service as required by the standards.
Repository-wide baseline is now **18 pre-existing lint violations** in untouched
files and the same **nine formatting differences**; no unrelated formatting was
applied. Live Edge network requests were mocked, as required by this gate. No
claim of online availability, actual FFmpeg conversion, or offline inference.
Native WAV routing remains explicitly rejected until M03 adds tested conversion.

Acceptance: existing Edge generation passes the complete regression suite.
Next milestone: M03 Piper, retaining Kokoro-82M as the quality priority in M04.

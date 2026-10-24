# M01 — Baseline Review and Architecture

Status: DONE. The [tracker](MILESTONE_TRACKER.md) is the source of truth.

## Objective

Baseline application still works and architecture decisions are documented.

## Scope

Implement only the tasks below, preserving the existing workflows. Follow the
[master plan](MASTER_PLAN.md) and [coding standards](../CODING_STANDARDS.md).

## Dependencies

Repository review and the existing application.

## Tasks

- Review existing implementation.
- Record existing functionality.
- Document current architecture.
- Introduce baseline regression tests.
- Define provider contracts.
- Create milestone tracker.

## Implementation constraints

Preserve Tkinter, Edge TTS, CLI defaults, and FFmpeg separation. No unnecessary
application rewrite, mandatory paid/cloud API, GPU dependency, or automatic
commit/push. Keep Kokoro-82M the natural-quality CPU target and Piper the
lightweight offline alternative without changing the milestone sequence.

## Acceptance criteria

Baseline application still works and architecture decisions are documented.

Pass the [shared coding standards gate](MASTER_PLAN.md#shared-compliance-gate)
and record exact evidence before DONE. Missing required validation blocks DONE.

## Test plan

Run the existing suite; add entry-point and cancellation regressions. Check new Python files with Ruff. Review UI startup and document external prerequisites.

## Expected deliverables

`docs/architecture/CURRENT_STATE.md`, `docs/architecture/PROVIDER_CONTRACT.md`,
M01–M10 milestone documents, baseline regression tests, and tracker evidence.

## Risks

Incomplete baseline evidence, missing FFmpeg, and a stale virtual environment.

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

2026-10-24: M01 completion gate passed.

- Reviewed all entry points, Python modules, requirements, build script, README,
  test modules, master instructions, standards, and tracker.
- Added CURRENT_STATE and PROVIDER_CONTRACT architecture documents and all ten
  milestone documents. Retained existing package/UI/adapter structure.
- Added five baseline regressions in `tests/test_baseline.py`: CLI ordered
  generation/default voices/progress; recombine sorting; empty recovery safety;
  cancellation preserving final output; full validation before side effects.
- Before changes: 44 tests passed in 0.55 seconds.
- After changes: 49 tests passed in 1.46 seconds.
- A real Tkinter window was constructed, withdrawn, checked for title/two voice
  rows/Ready state, and destroyed successfully. No live Edge request was made.
- Manual review: new tests have descriptive names, explicit flow, focused
  responsibilities, annotations, and no compressed statements. Application
  behavior and existing uncommitted work are preserved.

Commands (system Python 3.14.7; pytest 9.1.1; Ruff 0.17.2):

```powershell
$env:PYTHONPATH = "$(Resolve-Path .venv/quality-tools);$(Resolve-Path .venv/Lib/site-packages)"
python -m pytest -q --basetemp=.venv/m01-after -o cache_dir=.venv/m01-cache
python -m ruff check tests/test_baseline.py
python -m ruff format --check tests/test_baseline.py
python -m ruff check . --statistics
python -m ruff format --check . --output-format concise
```

Relevant Ruff checks pass. Repository-wide Ruff retains the pre-existing
26 violations and nine formatting differences documented in the
[adoption report](CODING_STANDARDS_VALIDATION.md); no application Python files
were changed in M01. Tests and Tkinter construction ran outside the sandbox to
avoid Windows asyncio/temp-directory restrictions.

Acceptance: baseline behavior is preserved under controlled adapter regressions
and real UI construction; architecture and provider decisions are documented.
No real-model test applies to the baseline. Live online synthesis, actual FFmpeg
media generation (FFmpeg absent on PATH), packaged executable testing, and human
listening were not part of this baseline gate and are not claimed as passing.
Future offline/export milestones must validate real media and runtime behavior.
No performance claim is made from unit-test timing. Next milestone: M02.

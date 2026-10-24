# Coding Standards Adoption Validation

Date: 2026-10-24. Scope: agent instructions, coding standards, milestone gates,
and developer tooling configuration. No application or test Python files were
edited. No commit or push was performed. Existing untracked instructions,
standards, master implementation instructions, and configuration were extended.

## Documentation and configuration

- `AGENTS.md` is the mandatory Codex session entry point.
- `docs/CODING_STANDARDS.md` is the authoritative coding convention source.
- The master plan retains all ten existing roadmap scopes and acceptance criteria.
- Every milestone and tracker row references the mandatory compliance gate.
- No tracker/status history existed; statuses remain explicitly unrecorded.
- Ruff targets Python 3.10, matching the README compatibility floor. Its rule
  selection is preserved; no lint rules were disabled to hide findings.
- Ruff discovery covers Python, stubs, notebooks, and `pyproject.toml`.
  Markdown counterexamples in the standards are explanatory documentation,
  not Python files to format.
- pytest uses `tests`, requires version 8+, validates configuration/markers, and
  registers `integration` and `real_model` without automatically skipping tests.
- Validation parsed TOML, checked local Markdown links and balanced code fences
  across seven documents, and confirmed that all ten original milestone scopes
  and acceptance criteria remain intact with a compliance check for each.
- Git whitespace checks pass, and the tracked Python diff is empty.

## Environment and reproducible commands

The existing `.venv` launcher references the missing `C:\Apps\Python\python.exe`.
Validation used installed system Python 3.14.7 with the existing environment's
pytest 9.1.1 and application dependencies through a process-local `PYTHONPATH`.
Ruff 0.17.2 was installed into ignored `.venv/quality-tools`; the existing
virtual environment was not recreated or replaced.

```powershell
$env:PYTHONPATH = "$(Resolve-Path .venv/quality-tools);$(Resolve-Path .venv/Lib/site-packages)"
python -m ruff check . --output-format concise
python -m ruff format --check . --output-format concise
python -m pytest -q --basetemp=.venv/pytest-standards-unrestricted -o cache_dir=.venv/pytest-standards-unrestricted-cache --tb=short
```

Tests ran outside the sandbox: **44 passed in 0.83 seconds**. The initial sandbox
attempt could not use the default temporary/cache directories; an attempt with
workspace temporary directories also failed the background-worker timeout and
stalled during asyncio tests. The complete unrestricted run passed without
application changes. Cache and temporary directory overrides are local
validation accommodations, not changes to the project's pytest policy.

Real-model inference, online Edge synthesis, FFmpeg playback, and packaged
Windows smoke tests were not run for this documentation/configuration change.
Those remain mandatory in the relevant feature milestones.

## Pre-existing lint violations

Ruff reports **26 violations**, all in unchanged Python files. Rechecking with
the original Python 3.12 target yields the same rule counts. These are recorded
separately rather than fixed through an unrelated source rewrite.

| File | Rule and count |
| --- | --- |
| `main.py` | I001: 1 |
| `tests/test_parser.py` | I001: 1 |
| `ttsapp/audio_combiner.py` | UP006: 2, UP035: 1 |
| `ttsapp/gui.py` | UP006: 2, UP035: 1, UP037: 1, UP045: 1 |
| `ttsapp/parser.py` | UP006: 5, UP015: 1, UP035: 2 |
| `ttsapp/service.py` | UP006: 3, UP035: 3, UP045: 2 |

Rule meanings: I001 import ordering; UP006 built-in collection annotations;
UP015 redundant file mode; UP035 deprecated typing imports; UP037 quoted
annotations; UP045 optional union annotations. Ruff passing is not claimed.

## Pre-existing formatting differences

Ruff reports **nine unchanged Python files** requiring formatting:

- `gen_audio.py`
- `main.py`
- `tests/test_audio_combiner.py`
- `tests/test_gui.py`
- `tests/test_parser.py`
- `tests/test_tts_engine.py`
- `ttsapp/audio_combiner.py`
- `ttsapp/gui.py`
- `ttsapp/parser.py`

Seven other Python files pass formatting. TOML configuration was parsed and
validated separately.
No formatter or automatic lint fix was applied to application/test code.

## Review outcome

This update establishes the policy and checks without claiming repository-wide
Ruff compliance or completing an application milestone. Future milestone work
must pass checks for changed Python files, report unrelated baseline findings,
and satisfy the readability, testing, architecture, and acceptance gates.


## Latest implementation review — 2026-10-25

The historical baseline counts above are preserved. Current results are
212 passing tests/nine opt-in skips, with real model/package evidence recorded
in the milestone documents. Two pre-existing I001 findings remain in `main.py`
and `tests/test_parser.py`; five formatting differences remain in those files
plus `gen_audio.py`, `tests/test_audio_combiner.py`, `tests/test_tts_engine.py`.
New/changed Python passes relevant Ruff and readability review. No rules were
disabled and no unrelated bulk formatting occurred. M01-M09 are DONE; M10 is
BLOCKED on clean Windows 11 validation, explicitly unavailable to the user.
See [consolidated status](../IMPLEMENTATION_STATUS.md).

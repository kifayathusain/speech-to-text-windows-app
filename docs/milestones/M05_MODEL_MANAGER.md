# M05 — Model Library and Download Manager

Status: DONE. The [tracker](MILESTONE_TRACKER.md) is the source of truth.

## Objective

A fresh installation can download, validate, use, and remove supported models without administrator privileges.

## Scope

Implement only the tasks below, preserving the existing workflows. Follow the
[master plan](MASTER_PLAN.md) and [coding standards](../CODING_STANDARDS.md).

## Dependencies

M04 must pass its completion gate before implementation starts.

## Tasks

- Implement model catalog.
- Add integrity-verified downloads.
- Add installation, deletion, and recovery.
- Add model management UI.

## Implementation constraints

Preserve Tkinter, Edge TTS, CLI defaults, and FFmpeg separation. No unnecessary
application rewrite, mandatory paid/cloud API, GPU dependency, or automatic
commit/push. Keep Kokoro-82M the natural-quality CPU target and Piper the
lightweight offline alternative without changing the milestone sequence.

## Acceptance criteria

A fresh installation can download, validate, use, and remove supported models without administrator privileges.

Pass the [shared coding standards gate](MASTER_PLAN.md#shared-compliance-gate)
and record exact evidence before DONE. Missing required validation blocks DONE.

## Test plan

Run focused unit and integration tests for the listed tasks, failure/cancellation/cleanup paths, and the complete regression suite. Use real assets/executables for relevant acceptance criteria; record manual Windows or listening checks separately.

## Expected deliverables

Implementation and behavior tests within this milestone's scope, updated
architecture/setup documentation where needed, and a completed tracker evidence
entry. No generated model/audio binaries in Git.

## Risks

Corrupt or interrupted downloads, unsafe paths, mismatched checksums, and incomplete license metadata.

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

2026-10-24: Gate passed after M04.

Implemented a quality-first trusted model catalog with versions, provider IDs,
source URLs, expected filenames/sizes/SHA-256, voices/languages, runtime and
licensing/attribution metadata. Provider descriptor factories now share this
catalog rather than duplicating trusted hashes. No inference model is loaded
merely because a directory contains files.

`ModelManager` supports explicit download progress/cancellation, verified atomic
activation, installation status and corruption checks, safe selected removal,
reinstallation, interrupted staging cleanup and verified backup recovery. OS
file locks prevent competing same-model transactions. All recursive removal
and directory activation targets are resolved inside the intended model root.
Default storage is app-specific LOCALAPPDATA without administrator requirements.

Added a Tkinter model-library window with catalog/status/size/license/runtime
information, Download/Reinstall, Cancel, Verify, and confirmed Remove. Network,
hashing, installation, and removal happen in workers; widgets update via the
main-thread queue. Original main-window generation and Edge defaults remain.
See [setup](../setup/MODEL_LIBRARY.md) and [architecture](../architecture/ARCHITECTURE.md).

Validation:

```powershell
python -m pytest -q --basetemp=.venv/m05-final -o cache_dir=.venv/m05-cache --tb=short
$env:TTS_MODEL_DOWNLOAD_TESTS = '1'
.\.venv\python313-official\python.exe -m pytest -q tests/test_model_manager_integration.py --basetemp=.venv/m05-fresh -o cache_dir=.venv/m05-real-cache --tb=short
```

Default full suite: **123 passed, four opt-in real-model cases skipped in 2.06s**.
Fresh real acceptance: **two passed in 60.94s**. Each catalog model was downloaded
through the actual manager into empty workspace storage, all files verified,
used for local CPU speech with Python network helpers denied during inference,
then removed. This validates user-writable installation, not a clean OS or final
packaged distribution (M10). Download networking is intentionally allowed during
installation; no administrator operation was required.

Unit tests cover invalid source/path/ID, short/oversized/corrupt downloads,
reinstallation, preservation on failure, cancellation cleanup, atomic activation
rollback, crash backup recovery, invalid-backup recovery, competing manager lock,
and unrelated-directory preservation. The worker test confirms no cross-thread
widget calls. Real Tkinter main/library windows constructed and background
verification delivered through the event loop successfully; an initial smoke
assertion before the 100ms UI poll was corrected by allowing the timer to run.

All 11 relevant Python files pass Ruff lint/format. Full checks retain ten
pre-existing lint violations and seven formatting differences in untouched
files. Existing GUI annotations/formatting were modernized only because that
module changed in scope. Manual readability, responsibility, error handling,
path/transaction safety, cleanup, and architecture review pass. No binaries,
unrelated refactor, commit, or push were added.

Acceptance: both supported models can be downloaded, verified, used, and removed
from fresh user-writable storage. Remaining limits: optional runtime installation
is separate; cancellation waits for a current network read/inference boundary;
model files in active sessions should be closed before removal. Next: M06.

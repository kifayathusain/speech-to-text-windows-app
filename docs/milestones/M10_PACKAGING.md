# M10 — Windows Packaging and Final QA

Status: BLOCKED. The [tracker](MILESTONE_TRACKER.md) is the source of truth.

## Objective

A clean Windows 11 environment can install, launch, download a model, synthesize offline audio, and export playable files.

## Scope

Implement only the tasks below, preserving the existing workflows. Follow the
[master plan](MASTER_PLAN.md) and [coding standards](../CODING_STANDARDS.md).

## Dependencies

M09 must pass its completion gate before implementation starts.

## Tasks

- Package the application for Windows.
- Include or securely locate FFmpeg.
- Keep downloadable models separate from the base installer.
- Validate a clean-machine installation.
- Complete regression tests.
- Update documentation.

## Implementation constraints

Preserve Tkinter, Edge TTS, CLI defaults, and FFmpeg separation. No unnecessary
application rewrite, mandatory paid/cloud API, GPU dependency, or automatic
commit/push. Keep Kokoro-82M the natural-quality CPU target and Piper the
lightweight offline alternative without changing the milestone sequence.

## Acceptance criteria

A clean Windows 11 environment can install, launch, download a model, synthesize offline audio, and export playable files.

Pass the [shared coding standards gate](MASTER_PLAN.md#shared-compliance-gate)
and record exact evidence before DONE. Missing required validation blocks DONE.

## Test plan

Run focused unit and integration tests for the listed tasks, failure/cancellation/cleanup paths, and the complete regression suite. Use real assets/executables for relevant acceptance criteria; record manual Windows or listening checks separately.

## Expected deliverables

Implementation and behavior tests within this milestone's scope, updated
architecture/setup documentation where needed, and a completed tracker evidence
entry. No generated model/audio binaries in Git.

## Risks

Missing dynamic libraries, model/voice license obligations, optional runtime packaging, and clean-machine failures.

## Completion checklist

- [ ] Tasks and acceptance criteria verified.
- [x] Relevant Ruff lint and formatting checks pass for changed Python files.
- [x] Existing and changed-behavior tests pass, including applicable errors,
      cancellation, and cleanup.
- [ ] Required real-model/FFmpeg/Windows checks are recorded where applicable.
- [x] Manual readability and architecture review passes.
- [x] Pre-existing violations and remaining limitations are recorded separately.
- [x] Documentation and tracker are updated with reproducible evidence.

## Validation evidence

Implemented and validated locally 2026-10-25. **BLOCKED only on the required
clean Windows 11 acceptance environment**, which is unavailable here (Windows
Sandbox executable is absent). This is not a claim that a separate clean host
passed. The user has the concrete artifact/checklist and explicitly confirmed:
“A clean Windows 11 machine is not available.” Do not mark DONE until that evidence is recorded.

## Implemented package

- `build-windows.ps1`: full/Edge profiles, prerequisite checks, fresh output
  directories, isolated PyInstaller work/spec paths, no deletion of old builds,
  optional explicit media bundling, binary/ZIP hashes, archive completeness and
  no-model-weight checks. `requirements-build.txt` includes CPU dependencies.
- `build_hooks/hook-piper.py`: CPU/eSpeak resources with Hebrew/Arabic auxiliary
  weights excluded. ONNX demo models are also excluded; no GPU binaries bundled.
- `runtime_paths.py`: verifies bundled tool hashes, supports BOM manifests and
  preserves source/external-PATH behavior. `app.py` retains Tkinter startup and
  adds explicit diagnostics; damaged tools receive recovery guidance.
- `diagnostics.py`: real provider/model/export acceptance report, downloads only
  on explicit CLI flags, nonzero failure status, no report overwrite, no
  invented clean-machine result. Existing default CLI entry points are intact.
- `scripts/package_notices.py`: dependency closure/version metadata, available
  upstream license texts and Python license. No application license is assigned.
  Public distribution requires resolving GPL compatibility/corresponding-source
  obligations; this unpublished local QA artifact is not a release approval.
- New tests cover media integrity, missing models, damaged tools, report
  preservation and extracted-executable inference. See
  [package setup and clean-machine checklist](../setup/WINDOWS_PACKAGE.md).

## Concrete review artifact

`dist/m10-qa-03/WindowsTTSApp-windows-x64.zip`, **148,750,055 bytes**.
SHA-256: `1d6c0ecda880f45eb38c0727164b37373110cc479b7b0a028d4946abca68f53f`.
The extracted folder is `.venv/m10-extracted-03/WindowsTTSApp`. ZIP contains
2,032 files, no `.onnx`/`.bin` weights and no CUDA DLLs. Models remain in separate
user storage. All older build artifacts were preserved.

Build command (working signed Python 3.13.17 and Tcl/Tk 8.6.15):

```powershell
.\build-windows.ps1 -PythonExecutable .venv/m10-tools/python313/python.exe -OutputDirectory dist/m10-qa-03 -FFmpegDirectory .venv/ffmpeg-toolset
```

Original `.venv` remains stale and untouched. The isolated build interpreter
uses the official signed Python embeddable runtime plus official signed Tcl/Tk
MSI files extracted without global installation. Tcl/Tk MSI SHA-256:
`ae3e5f9dd998b36d14655cd3444d0af906c1849c60aee40994eeb1e460a3cabf`.
Unsigned managed Python DLLs blocked by Windows policy were not used or bypassed.
PyInstaller 6.22.3 built the folder. The embedded Python/Tk binaries are signed;
the application executable itself is unsigned. FFmpeg/FFprobe 9.0.2 are the
previously verified Gyan essentials build; its license/source information and
per-binary hashes are included. Nothing was committed, pushed or published.

## Automated and actual Windows verification

- Eight new focused startup/media/diagnostics tests pass.
- Final complete suite: **212 passed, nine opt-in skips**, 22.24s:
  `python -m pytest -q --basetemp=.venv/m10-final-full
  -o cache_dir=.venv/m10-final-cache --tb=short`, using quality-tool/original
  site-packages PYTHONPATH, real toolset PATH, and `TTS_EXPORT_TESTS=1`,
  `TTS_FFMPEG_TESTS=1`, `TTS_PLAYBACK_TESTS=1`.
- Extracted build 02, fresh model root, cleared Python/Tcl paths and minimal
  Windows PATH: `TTS_PACKAGE_EXE=.venv/m10-extracted-02/WindowsTTSApp/WindowsTTSApp.exe`
  with `python -m pytest tests/test_windows_package_integration.py -q
  --basetemp=.venv/m10-package-real -o cache_dir=.venv/m10-package-cache --tb=short`:
  **one passed**, 106.61s. Freshly downloaded both catalog models; real Kokoro and
  Piper native synthesis plus validated WAV/MP3/M4A pass.
- Final build 03, same cleared environment, reused freshly verified QA model
  library: `WindowsTTSApp.exe --diagnostics <empty-report-dir>
  --model-root <qa-models> --check-edge`: **exit 0**, all three real providers
  and all nine exports pass. [Exact report](../performance/M10_PACKAGE_ACCEPTANCE.json)
  distinguishes initial-download and final-artifact hashes/results.
- Native UI inspection via computer-use skill: desktop opens, controls are
  visible, Model library opens/lists separate model downloads, Kokoro selection
  exposes local voices/speed, missing-model preview offers actionable recovery,
  and graceful closure removes the window. Final archive startup also verified.
  This inspection does not establish offline playback on a clean OS.
- Relevant Ruff lint/format commands on `app.py`, `runtime_paths.py`,
  `diagnostics.py`, `package_notices.py`, the build hook and four new test files:
  pass, nine files already formatted. PowerShell parse check: zero errors.
  Repository-wide Ruff retains only two existing I001 findings in `main.py`
  and `tests/test_parser.py`, and five existing formatting differences in those
  plus `gen_audio.py`, `tests/test_audio_combiner.py`, `tests/test_tts_engine.py`.
- Documentation/TOML validation passes: local links, fences and every milestone's
  required sections checked. Manual review confirms focused modules, explicit
  errors/control flow, appropriate hints/docs, lifecycle cleanup, no compressed
  Python or unrelated formatter changes, and preserved UI/service/CLI boundaries.

## Unmet acceptance and next action

Follow the clean Windows 11 checklist in package setup on a separate machine/VM.
Record fresh downloads, offline preview/playback/synthesis, every export format,
Edge after reconnecting, cancellation/close, persistence and OS/package identity.
The diagnostic report intentionally leaves `clean_machine_confirmed=false`.
No OS network adapter/security settings were changed. M06's accepted joins and
M09's real CPU regressions remain valid, but cannot substitute for this gate.
All M01-M09 statuses and completed work remain DONE. No later milestone starts.


# M11 — Complete British and American English Voice Library

Status: DONE. The [tracker](MILESTONE_TRACKER.md) is authoritative.

## Objective and authorization

Expose every British and American English voice in the pinned official
Kokoro-82M v1.0 and Piper catalogs for download, preview, and generation.
The user explicitly authorized M11 on 2026-10-25 while M10 remains BLOCKED
on clean Windows 11 acceptance. This follow-up does not waive M10's gate or
change M01–M09's historical statuses.

## Scope

- Kokoro: all 20 American and eight British English voices, verified against
  the existing ONNX voice archive; reuse the shared model installation.
- Piper: every en_US/en_GB model and quality variant in official revision
  `5041a7a49ae5b3a0f30e6837769eb03fdbb231bd`, including all individual speakers.
  The inventory has 38 model variants and 2,006 selectable speaker/variant pairs.
  The index incorrectly advertises 2,306 LibriTTS-R speakers, whereas its
  hash-verified configuration defines 904. Configuration maps are authoritative
  for synthesis; the snapshot retains both counts for auditability.
  Locale labels follow upstream model metadata; individual training speakers
  in multispeaker datasets may have other native accents.
- Pinned HTTPS sources, sizes, SHA-256, model cards and per-model licensing.
- Lazy selected-model loading, explicit speaker selection, preview cache
  separation, searchable desktop voices, and per-model installation guidance.
- Keep existing IDs/defaults where possible, especially Lessac low; preserve
  Edge, FFmpeg separation, user installations, cancellation and cleanup.

## Implementation sequence

1. Generate a reviewed, reproducible offline Piper metadata snapshot.
2. Expand Kokoro metadata and manifest voice inventory from one shared source.
3. Build Piper manifests/descriptors from the snapshot and select speakers.
4. Remove the desktop's one-Piper-model assumption; add voice search and model
   status without hashing weights or performing network I/O on the UI thread.
5. Add catalog, provider, UI and real-model acceptance coverage and documentation.
6. Record checks and unresolved acceptance gaps before assigning DONE.

## Acceptance criteria

- Exact pinned inventory coverage: 28 Kokoro voices and every Piper English
  model/quality/speaker pair; no silent omissions or duplicate IDs.
- All choices discoverable offline before installing optional inference runtimes.
- Search and en-US/en-GB filters work; missing/corrupt selected models receive
  actionable Model library guidance, and unrelated missing models do not block use.
- Piper selects the requested speaker, reuses sessions within a model, releases
  sessions across models and validates speaker IDs against verified configs.
- Existing verified installations remain usable; downloads preserve atomic
  integrity checks, cancellation, cleanup, removal and model-specific notices.
- Real CPU synthesis produces nonempty valid WAV for every exposed voice/speaker
  with Python network calls denied during inference; representative exports and
  Windows preview/mixed-model generation pass. Record listening separately.
- Pass the [coding standards gate](../CODING_STANDARDS.md#20-tooling-and-milestone-completion-gate),
  complete regressions, changed-file Ruff and manual architecture/readability review.

## Sources and maintenance

- [Kokoro official voices](https://huggingface.co/hexgrad/Kokoro-82M/blob/c3327e9bac3dbe55779397bfa82de0f8806fb3bc/VOICES.md).
- [Pinned Piper inventory](https://huggingface.co/rhasspy/piper-voices/blob/5041a7a49ae5b3a0f30e6837769eb03fdbb231bd/voices.json).
- `python -m scripts.update_english_voice_catalog` refreshes the metadata snapshot
  from an explicit revision for developer review. Application startup performs
  no online discovery. New upstream additions require a reviewed catalog update.

## Validation evidence

Implementation and the M11 completion gate passed on 2026-10-25. All 2,034
voice choices passed actual CPU synthesis checks; Windows UI, exports, native
playback, regression checks, scoped Ruff and standalone package QA passed.
Human listening is separate, and M10 clean-machine acceptance remains BLOCKED.

## Completion checklist

- [x] Acceptance criteria pass, including every pinned voice/speaker and the
      applicable real-model/Windows checks recorded below.
- [x] All 17 changed/new Python files pass Ruff lint and formatting; exact
      commands/results are recorded below.
- [x] Repository-wide Ruff checks and the existing suite ran; the two baseline
      import findings/five formatting differences remain separately listed.
- [x] New and existing tests cover behavior, failures, cancellation and cleanup;
      full suite 235 passed/11 opt-in skips, with real acceptance separately run.
- [x] Manual review confirms descriptive names, focused responsibilities,
      appropriate types/docstrings, explicit errors and control flow, and no
      compressed statements or unnecessary abstractions.
- [x] Existing features, module boundaries, user installations and earlier
      artifacts are preserved. Temporary validation models were cleaned up.
- [x] Architecture/setup docs, tracker, source notices and validation evidence
      are current; remaining limitations and M10's independent blocker are clear.

### Implementation and regression checks — 2026-10-25

The trusted inventory and provider factories now share the pinned voice data.
All 28 Kokoro styles are retained from the already-verified archive. Piper has
38 independently installable model variants, numeric speaker descriptors,
configuration-bound session reuse, lazy selected-installation checks, and
actionable missing/corrupt-model errors before both synthesis and cached preview.
Existing Kokoro/Lessac installation IDs, versions and asset hashes remain valid.

The desktop searches names, quality and upstream speaker names, retains accent
filtering, and shows the required model/presence below each voice. Model library
has search, scrolling, per-model licensing and bounded speaker details. Presence
is explicitly a hint; hashing, model verification, downloads and inference stay
in workers. Main-window requested height remains below its default 760 pixels.
The Windows build includes the offline JSON inventory via an absolute data path.

Regression coverage includes exact inventory/counts, stable IDs, upstream
index/config discrepancy, locale/quality/speaker search, shared-model reuse,
configuration/model switching, invalid speaker IDs, selected-installation
validation, corrupt cached-preview prerequisites, metadata integrity and
catalog-bound validation resume. Existing download transaction, corruption,
cancellation, worker cleanup, preview and export regressions remain in the suite.

Final regression command (Python 3.14.7, pytest 9.1.1, Ruff 0.17.2):

```powershell
$env:PYTHONPATH = "$(Resolve-Path .venv/quality-tools);$(Resolve-Path .venv/Lib/site-packages)"
$env:PATH = "$(Resolve-Path .venv/ffmpeg-toolset);$env:PATH"
$env:TTS_EXPORT_TESTS = '1'
$env:TTS_PLAYBACK_TESTS = '1'
python -m pytest -q --basetemp=.venv/m11-final-complete -o cache_dir=.venv/m11-cache --tb=short
```

Result: **235 passed, 11 opt-in skips in 24.73 seconds**, including native
Windows playback and actual codec/media tests. The opt-in skips are older
provider/download/preview/long-form/desktop/package acceptance tests, the new M11
UI test (passed separately above), and an older FFmpeg processing opt-in test.
Relevant real M11 checks run separately with the signed Python 3.13 runtime.
No skipped test is counted as passing.

All 17 changed/new Python files pass both Ruff checks. Exact scoped commands:

```powershell
$taskPythonPaths = @((git -c core.fsmonitor=false diff --name-only -- '*.py'), (git -c core.fsmonitor=false ls-files --others --exclude-standard -- '*.py')) | ForEach-Object { $_ } | Where-Object { $_ }
python -m ruff check @taskPythonPaths
python -m ruff format --check @taskPythonPaths
python -m ruff check . --output-format concise
python -m ruff format --check . --output-format concise
git -c core.fsmonitor=false diff --check
```

Repository-wide results preserve the baseline: I001 in `main.py` and
`tests/test_parser.py`; formatting differences in `gen_audio.py`, `main.py`,
`tests/test_audio_combiner.py`, `tests/test_parser.py`, `tests/test_tts_engine.py`.
No unrelated formatting, lint suppression or new violations. Diff whitespace
checks pass. Manual review confirms descriptive names, focused typed boundaries,
explicit errors/control flow, no compressed statements, and preserved
UI/model/provider/audio responsibilities. No commit or push.

### Real Windows UI and standalone package

Command (signed Python 3.13.17, real Piper and FFmpeg/FFprobe on PATH):

```powershell
$env:TTS_M11_MODEL_ROOT = (Resolve-Path .venv/m11-models).Path
.\.venv\m10-tools\python313\python.exe -m pytest tests/test_english_voices_integration.py -q --basetemp=.venv/m11-gui-02 -o cache_dir=.venv/m11-gui-cache --tb=short
```

Result: **one passed in 21.63 seconds**. Real Tkinter search selected ARU speaker
11; two speakers generated distinct actual PCM previews/cache entries; the event
loop remained active; Alan (British) and Lessac (American) generated one script
and valid WAV/MP3/M4A exports. Model library search/licensing and graceful worker
closure passed. Preview playback dispatch was observed with a controlled player;
native Windows playback is checked separately. No listening/quality claim.

Local full QA package:

```powershell
.\build-windows.ps1 -PythonExecutable .venv/m10-tools/python313/python.exe -OutputDirectory dist/m11-qa-03 -FFmpegDirectory .venv/ffmpeg-toolset
```

`dist/m11-qa-03/WindowsTTSApp-windows-x64.zip`: **148,778,759 bytes**, SHA-256
`7656bd01335b3dcf1f47db83ccf20fa99ba6a43ebf67385ae8b1d89161b413d1`.
ZIP has 2,033 files; its bundled Piper snapshot is byte-identical to source and
contains all 38 variants. Standalone diagnostics, with development Python/Tcl
environment variables removed and only Windows directories on PATH, exited 0.
Both providers used pre-existing M10 model installations successfully and
exported valid PCM WAV, MP3 and AAC/M4A. Report:
`.venv/m11-package-report/acceptance.json`. This is development-host QA, not
clean-machine acceptance, signing or public release; M10 remains BLOCKED.

### Exhaustive real-model command

```powershell
.\.venv\python313-official\python.exe -m scripts.validate_english_voices --model-root .venv/m11-models --kokoro-dir .venv/validation-models/kokoro --output .venv/m11-acceptance-03 --remove-after-check
```

The explicit validation command downloads verified Piper assets, denies Python
DNS/socket connections during each inference loop, checks nonempty/nonzero mono
16-bit PCM for every choice, closes the provider and removes its temporary Piper
installation before continuing. One representative WAV per model is retained;
all per-speaker metrics are recorded in the JSON report. `--resume` continues
after a download interruption only when the catalog digest and completed voice
lists match exactly. It is a developer validation command, never app startup.
The remaining American checks resumed with `--resume --sample-text 'Hello.'`;
earlier completed checks used the default full sentence. A second independent
CPU process used the same `check_provider` helper, catalog and verified model
manager in `.venv/m11-secondary-models`, writing
`.venv/m11-secondary-acceptance/report.json`. It overlapped the remaining models
with LibriTTS high. No concurrent synthesis shared a provider or installation.
The primary process was stopped after its LibriTTS high result was saved, before
repeating the independently completed LibriTTS-R model. The reports are combined
only after catalog identity and exact voice-set checks.

Environment: Windows 11 development host, signed Python 3.13.17, Piper 1.8.0,
kokoro-onnx 0.6.1, ONNX Runtime 1.31.0 CPU, NumPy 2.5.4. No OS adapter was disabled;
the precise offline claim is denial of Python DNS/connection helpers during
local CPU inference. Model installation intentionally uses the network.

### Resolved validation obstacles

The sandbox's Windows asyncio socket pair hung; tests requiring event loops ran
outside that restriction. An early repeated-output acceptance loop hit a Windows
file lock; the harness now uses separate output names. Initial package attempts
exposed a relative PyInstaller data path and exhausted disk space. The data path
is now absolute; only this run's incomplete build directories were removed, and
temporary validation models are removed after checks. Earlier user artifacts
were preserved. One upstream download reset required a resumable continuation.
These failed attempts are not counted as passes; final evidence uses the paths
and commands above.


### Exhaustive completion results — 2026-10-25

**All 2,034 choices passed**: 28 Kokoro voices and 2,006 Piper speaker/quality
choices across all 38 pinned English Piper models. No advertised choice is
unaccounted for. Every check produced nonempty, nonzero mono 16-bit PCM while
Python network connection helpers were denied. Models used explicit CPU sessions.

Combined evidence: `.venv/m11-acceptance-03/complete-report.json`.

Combined report SHA-256: `73649e9ba18af6c3df2348c4348b528472659539f0715b0981460b9d0cba9cde`.

The two source reports are retained; their catalog identities match and their
model sets are disjoint. The combined report was checked against every manifest
and exact ordered voice ID list, with positive durations/sample rates. One WAV
per model remains for inspection; per-speaker audio was removed after validation.

| Model | Locale | Passed choices | PCM rate (Hz) |
| --- | --- | ---: | ---: |
| kokoro-82m-v1 | en-US, en-GB | 28 | 24000 |
| piper-lessac-low | en-US | 1 | 16000 |
| piper-en_gb-alan-low | en-GB | 1 | 16000 |
| piper-en_gb-alan-medium | en-GB | 1 | 22050 |
| piper-en_gb-alba-medium | en-GB | 1 | 22050 |
| piper-en_gb-aru-medium | en-GB | 12 | 22050 |
| piper-en_gb-cori-high | en-GB | 1 | 22050 |
| piper-en_gb-cori-medium | en-GB | 1 | 22050 |
| piper-en_gb-jenny_dioco-medium | en-GB | 1 | 22050 |
| piper-en_gb-northern_english_male-medium | en-GB | 1 | 22050 |
| piper-en_gb-semaine-medium | en-GB | 4 | 22050 |
| piper-en_gb-southern_english_female-low | en-GB | 1 | 16000 |
| piper-en_gb-vctk-medium | en-GB | 109 | 22050 |
| piper-en_us-amy-low | en-US | 1 | 16000 |
| piper-en_us-amy-medium | en-US | 1 | 22050 |
| piper-en_us-arctic-medium | en-US | 18 | 22050 |
| piper-en_us-bryce-medium | en-US | 1 | 22050 |
| piper-en_us-danny-low | en-US | 1 | 16000 |
| piper-en_us-hfc_female-medium | en-US | 1 | 22050 |
| piper-en_us-hfc_male-medium | en-US | 1 | 22050 |
| piper-en_us-joe-medium | en-US | 1 | 22050 |
| piper-en_us-john-medium | en-US | 1 | 22050 |
| piper-en_us-kathleen-low | en-US | 1 | 16000 |
| piper-en_us-kristin-medium | en-US | 1 | 22050 |
| piper-en_us-kusal-medium | en-US | 1 | 22050 |
| piper-en_us-l2arctic-medium | en-US | 24 | 22050 |
| piper-en_us-lessac-high | en-US | 1 | 22050 |
| piper-en_us-lessac-medium | en-US | 1 | 22050 |
| piper-en_us-libritts-high | en-US | 904 | 22050 |
| piper-en_us-libritts_r-medium | en-US | 904 | 22050 |
| piper-en_us-ljspeech-high | en-US | 1 | 22050 |
| piper-en_us-ljspeech-medium | en-US | 1 | 22050 |
| piper-en_us-mike-medium | en-US | 1 | 22050 |
| piper-en_us-norman-medium | en-US | 1 | 22050 |
| piper-en_us-reza_ibrahim-medium | en-US | 1 | 22050 |
| piper-en_us-ryan-high | en-US | 1 | 22050 |
| piper-en_us-ryan-low | en-US | 1 | 16000 |
| piper-en_us-ryan-medium | en-US | 1 | 22050 |
| piper-en_us-sam-medium | en-US | 1 | 22050 |

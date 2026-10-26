# M12 — JSON document contract and validation

Initial status: NOT_STARTED. Dependency: current architecture and shared rules reviewed. Scope: document layer only; do not implement generation or redesign the GUI yet.

## Objective

Parse, validate and serialize the sample's structured conversation without losing role identity, direction notes, text, timing or extension data.

## Implementation tasks

1. Introduce typed document, speaker, segment, speech-setting and diagnostic models, preferably in `ttsapp/conversation_document.py`. Keep these independent of Tkinter and inference libraries.
2. Provide file and in-memory parsing entry points with identical semantic validation. Read UTF-8/BOM, enforce file size before loading and enforce equivalent byte/count/depth limits for in-memory input. Guard excessive nesting before passing data into recursive conversion; avoid a naive brace count that misreads strings.
3. Reject duplicate object keys at every depth, malformed JSON, unsupported schema versions, non-object roots, empty/wrong-type arrays, missing required fields, duplicate IDs, bad references, wrong types and non-finite numbers. Validate optional fields only when present; absence is different from null or a wrong type.
4. Follow shared limits and defaults. Omitted direction is empty; omitted pause is zero; omitted speed remains unset. Reject whitespace-only role labels/text and IDs with surrounding whitespace. Preserve original dialogue rather than silently normalizing the saved source.
5. Return errors with semantic paths and stable diagnostic codes. Syntax errors also include line and column. Aggregate independent semantic errors up to a documented bound of 100, then report additional errors were omitted. Never include private source text in default logs.
6. Preserve unknown root/speaker/segment/nested extension fields and issue warnings. Keep immutable core state or defensive copies so worker snapshots cannot be mutated through retained input dictionaries.
7. Add a serializer and atomic Save As helper that preserve known and unknown fields and all segment ordering. New documents may write `schema_version: 1`. Saving a document must not perform synthesis or implicitly write to its imported path.
8. Publish `docs/tts-input.schema.json` and a concise format guide. Keep `docs/tts-sample.json` unchanged as the compatibility fixture. Add a small separate example covering optional defaults and speed.
9. Define active-document identity separately from revision/content hash. A new import has a fresh identity unless explicitly reloading the same active source; edits advance revision without changing identity. M15 will connect this to UI state; M16 persists project identity.

## Expected files

New document module, schema/format guide, example and `tests/test_conversation_document.py`; adjust existing modules only for a small shared adapter if needed. No runtime schema-validation dependency is required. Existing text parser behavior remains untouched.

## Required acceptance

- Unmodified sample parses into three speakers and 26 ordered segments; explicit pause sum is 84, including a final 30.
- Duplicate role labels with distinct IDs are legal; duplicate IDs are rejected.
- Missing and explicit zero pauses resolve correctly; fractional values round-trip without silent truncation.
- Version/type/reference/limit errors are actionable, including bool-as-number and `schema_version: true`.
- Unknown fields round-trip; known invalid fields cannot hide as extensions.
- BOM, Unicode, embedded colons, newlines and direction notes survive source round-trip.
- The depth check handles braces/quotes inside text and rejects excessive nesting cleanly.
- Parse/serialize uses no network, model files or provider initialization.
- Atomic save failure preserves the previous destination and cleans temporary data.

## Verification and completion

Add focused parser/serializer/error tests including size/depth/count boundaries and source-copy isolation. Run audited existing parser regressions and changed-file Ruff. Record exact evidence under M12. The document layer may return warnings for unused speakers; provider-specific mapping validity belongs to M13. Do not claim GUI import acceptance in this milestone.

## Implementation and acceptance evidence — 2026-10-26

Status: **DONE**. Dependency: repository instructions, coding standards, current
architecture, master plan, tracker, shared M12–M17 rules and existing parser,
service, provider and atomic-file boundaries reviewed before implementation.
No deeper AGENTS.md or test conftest files were found. Only M12 was implemented.

### Delivered scope

- `ttsapp/conversation_document.py`: typed frozen document/speaker/segment/speech
  and diagnostic models; bounded UTF-8/BOM file/text/Python-tree entry points;
  depth preflight; duplicate-key, version, type, identity/reference and numeric
  validation; bounded semantic error aggregation and extension/unused warnings.
- Immutable source snapshots preserve optional-field absence, original text,
  JSON numeric spelling, notes, pauses, array order and arbitrary nested
  extensions. Defensive `to_dict()` copies and read-only voice defaults prevent
  retained dictionaries from mutating worker state. New imports have fresh
  identities; edits/explicit reloads retain identity and advance revision;
  canonical content hashes remain independent of both.
- Serialization and explicit atomic Save As use no providers, models, network
  or widgets. Save As flushes/fsyncs before replacing and cleans its temporary
  file after failure. Imported paths are never implicit save destinations.
- `docs/tts-input.schema.json`, `docs/JSON_DOCUMENT_FORMAT.md` and a separate
  `docs/tts-input-example.json` publish the format, API, defaults and limits.
  Architecture/master-plan/tracker additions register the follow-up without
  changing historical milestone evidence/statuses.
- `tests/test_conversation_document.py` adds 148 offline cases. The committed
  [allowlist](M12_OFFLINE_TESTS.txt) records the complete 26-file regression scope.
  All existing application modules, entry points and legacy parser remain
  unchanged; no mapping, structured generation, GUI import or project feature
  is claimed here.

### Acceptance results

| Required behavior | Evidence/result |
| --- | --- |
| Unmodified sample | Three speakers, 26 ordered segments, total explicit pause 84 seconds and final pause 30; source dictionary round-trip passes |
| Role/ID/reference semantics | Duplicate display roles accepted; case-sensitive, unique, trimmed IDs and exact references tested |
| Defaults and numbers | Absent direction/pause/speed resolve to empty/zero/unset; explicit zero, fractional pause/speed and range endpoints round-trip; null, bool, numeric strings, NaN/infinity and unsupported versions fail |
| Optional/extension fields | Known invalid fields fail; root/speaker/segment/speech extensions round-trip with warnings, including nested extension payloads; warning bounds do not drop data |
| Encoding and text | BOM bytes/string/file entry points, Unicode, embedded colons/newlines, whitespace-preserving dialogue and direction notes pass; invalid UTF-8/surrogates fail cleanly |
| Structure and diagnostics | Duplicate keys at all depths (including escaped key aliases), malformed syntax with line/column, wrong roots/arrays/records, required fields and matching file/memory errors tested |
| Limits | Exact 10 MiB and over-limit UTF-8/file/tree cases, rejection before file read, 1,000/10,000 count endpoints, 64/65 container depths, quoted braces/escaped quotes, cyclic trees, 86,400-second cumulative limit and 100-plus-sentinel diagnostic bounds pass |
| Snapshot/identity | Retained input/output trees cannot mutate source; frozen records/read-only defaults, fresh import IDs, stable edit/reload IDs, revision/hash changes and invalid-edit isolation pass |
| Side effects and saves | Isolated cold module execution blocks provider/widget/socket imports; parse/serialize uses JSON only; explicit save preserves source; injected fsync/replace failures preserve destination and remove temporary files |

Sample SHA-256 (unchanged; Git diff empty):
`81e9d951bdd041e6e6b6dd487e928b85cd97abbde09a666280fe3019243a2dc8`.

### Environment and exact verification

Windows 11 development host (`Windows-11-10.0.26300-SP0`), CPython **3.13.17**,
pytest **9.1.1**, Ruff **0.17.2**, existing FFmpeg/FFprobe **9.0.2 essentials**.
The current `.venv/Scripts/python.exe` lacks pytest/Ruff; older documented
`.venv/m10-tools` and `.venv/python313-official` paths no longer exist. Existing
tools in `.venv-backup` were used without installing dependencies or tools.

Focused final command, from the repository root:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
.\.venv-backup\python313-official\python.exe -m pytest tests/test_conversation_document.py tests/test_parser.py -q --basetemp=.venv/m12-focused-complete -o cache_dir=.venv/m12-cache --tb=short
```

Result: **157 passed in 2.63 seconds** (148 new document cases and nine legacy
parser cases). Earlier focused iterations passed 150 and 152 cases before the
final assertions were added; they are not added to the final totals.

Final broad audited command:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:TTS_FFMPEG_TESTS = '1'
$env:TTS_EXPORT_TESTS = '1'
$env:PATH = (Resolve-Path .venv-backup/ffmpeg-toolset).Path + [IO.Path]::PathSeparator + $env:PATH
$m12Tests = Get-Content docs/milestones/M12_OFFLINE_TESTS.txt
.\.venv-backup\python313-official\python.exe -m pytest @m12Tests -q --basetemp=.venv/m12-regression-final -o cache_dir=.venv/m12-cache --tb=short
```

Result: **364 passed in 10.10 seconds**, no failures or skips. The same allowlist
passed 359 cases before the final five assertions/cases were added. An initial
sandboxed broad run stalled at the first legacy asyncio case after the focused
cases, consistent with the previously recorded Windows local socket-pair
restriction; it was interrupted, not counted as passing. Both completed broad
runs used approved execution outside the sandbox to permit asyncio's local
socket pair. Their exact basetemp directories were respectively
`.venv/m12-regression-unrestricted` and `.venv/m12-regression-final`.

Safety audit before collection/execution: no conftest files; automatic third-party
pytest plugins disabled; ambient opt-in environment names inspected (no TTS/model
switches present); only explicit reviewed files collected. Allowlisted provider
fixtures use mocked Edge Communicate/native MP3 and local WAV/runtime fakes;
model-manager transactions use tiny in-memory fake responses in temporary
directories. No live opener or inference engine runs. Subprocess lifecycle
tests execute only controlled Python children. The two enabled integration
files use generated non-speech sine/PCM fixtures and existing media tools only.
Headless desktop/worker tests use fake controls/providers; no M12 GUI acceptance
or live preview is claimed. Existing model installations/audio were not changed.

Ruff commands:

```powershell
.\.venv-backup\quality-tools\bin\ruff.exe format --check ttsapp/conversation_document.py tests/test_conversation_document.py
.\.venv-backup\quality-tools\bin\ruff.exe check ttsapp/conversation_document.py tests/test_conversation_document.py
.\.venv-backup\quality-tools\bin\ruff.exe format --check . --output-format concise
.\.venv-backup\quality-tools\bin\ruff.exe check . --output-format concise
git -c core.fsmonitor=false diff --check
```

Changed files: **two already formatted; all lint checks pass**. Repository-wide
format check: five pre-existing differences in `gen_audio.py`, `main.py`,
`tests/test_audio_combiner.py`, `tests/test_parser.py`, `tests/test_tts_engine.py`;
80 files already formatted. Repository lint: existing **I001** in `main.py:9`
and `tests/test_parser.py:1` only. No introduced findings, suppressions or bulk
formatting. Diff whitespace check passes. Both new Python files also parse with
`ast.parse(..., feature_version=(3, 10))`; Python 3.10 runtime execution was not
performed, and the declared compatibility floor/dependencies remain unchanged.

### Exclusions (not failures)

These files were not collected; no marker-only full-suite run was used:

| Excluded file(s), under `tests/` | Reason |
| --- | --- |
| `test_piper_integration.py`, `test_kokoro_integration.py`, `test_preview_integration.py`, `test_longform_integration.py` | Real-model/inference acceptance is prohibited for this follow-up |
| `test_model_manager_integration.py`, `test_windows_package_integration.py` | Real download/model/package acceptance can trigger prohibited activities |
| `test_gui_integration.py`, `test_gui_export_integration.py`, `test_english_voices_integration.py` | Historical real-provider Windows acceptance is outside M12 and the safe boundary |
| `test_diagnostics.py` | Diagnostics acceptance is outside the reviewed allowlist; diagnostic/build execution that might invoke real providers is excluded |
| `test_voice_validation_report.py`, `test_voice_catalog_updater.py`, `test_english_catalog.py` | Separate voice-validation/report/catalog maintenance regressions are not needed for the standalone document change; no exhaustive voice or quality work is repeated |
| `test_model_library.py` | Separate model-library GUI tests are outside the audited M12 allowlist; retained library behavior is covered here only through fake manager/provider boundaries |

No build/diagnostic acceptance commands, downloads, real inference, live Edge
synthesis, quality/listening/comparison tests, benchmarks or exhaustive voice
checks were performed. No dependencies/media tools were installed. The allowed
fake-provider/synthetic-media scope replaces historical real-voice requirements
for this follow-up only. No real-provider or clean-machine claim is made.

### Completion gate and limitations

- [x] All M12 acceptance criteria pass in the accepted offline scope.
- [x] Changed-file Ruff format/lint and manual readability review pass.
- [x] Repository-wide Ruff findings are recorded separately; no introduced issues.
- [x] Reviewed regression allowlist and changed-behavior tests pass, including
  invalid input, file failures, copy isolation and temporary cleanup. Document
  I/O is synchronous and has no cancellation API; existing fake-provider job,
  preview, worker and subprocess cancellation/cleanup regressions pass.
- [x] Manual review confirms meaningful names, focused typed responsibilities,
  useful public docstrings, explicit errors/control flow, no compressed statements
  or unnecessary abstractions, and no private-dialogue logging.
- [x] Existing UI/service/provider/model/audio boundaries and unrelated work are
  preserved. The source snapshot exists specifically to retain extensions and
  optional-field absence without mutable worker state or extra dependencies.
- [x] Format/schema/example, architecture, roadmap, tracker and exclusions updated.

Unmet M12 gates: **none**. Windows widget import acceptance, rendered segment
timing and final-pause audio export are later milestones; M12 verifies their
source data only. M10 remains independently BLOCKED on clean Windows 11 evidence.
Historical statuses/evidence remain unchanged. No commit or push.
Next dependency: M13 role-to-voice mapping, when explicitly requested. Stop here.

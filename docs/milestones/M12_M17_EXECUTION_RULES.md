# Shared execution rules for M12–M17

Apply these rules to every milestone in this packet. The approved feature is structured JSON input, editable multi-speaker mappings, explicit timing, and an improved Windows desktop workflow. Implement the smallest maintainable extension of current code.

## Review and status management

1. Read `AGENTS.md`, `docs/CODING_STANDARDS.md`, `docs/architecture/ARCHITECTURE.md`, the master plan, tracker and current milestone. Check for more-specific instructions in affected directories.
2. Inspect current implementations and tests. `CURRENT_STATE.md` is historical M01 evidence; do not overwrite it with a new baseline or assume later features are missing.
3. Preserve unrelated uncommitted work, current models, existing audio and historical evidence. No destructive Git operations, automatic commits, pushes or public releases.
4. Register M12–M17 using `TRACKER_ADDITIONS.md` when implementation starts. Do not mark a milestone DONE merely because files exist or its successor is being requested.
5. Implement sequentially. If an unmet gate prevents continuation, report it precisely; do not silently waive acceptance. Continue independent authorized work within the target scope where useful.
6. Follow repository naming, type hints, error handling, Python 3.10 compatibility, PEP 8 and Ruff policy. Avoid broad refactoring, suppressions, bulk formatting and speculative abstraction.

## Architecture and compatibility invariants

- Retain Tkinter/ttk, Edge, Piper, Kokoro, CPU-only local runtimes, the provider contract, model manager, FFmpeg/FFprobe and existing export modules.
- Use one selected provider per generation job. Multiple Piper model/speaker IDs remain supported within Piper through existing lazy sessions.
- Keep parsing, mapping, synthesis, model lifecycle, preview, audio processing and UI responsibilities separate. New module names in this packet are suggestions where equivalent responsibilities already exist.
- Preserve `app.py`, `main.py`, `gen_audio.py`, no-argument CLI behavior, existing defaults, `Speaker: text`, colon handling, Unicode, blank-line/paragraph semantics and unknown-speaker errors.
- Preserve the original unprocessed Edge path and stream-copy behavior when requests do not opt into structured processing. Structured JSON uses the processed path.
- Preserve public positional parameters and existing progress callback shape; use additive keyword-only inputs and defaulted fields where possible.
- Preserve native provider outputs, model verification, custom Edge voice-ID entry, stable local catalog voice IDs, preview/replay/stop, cancellation, worker cleanup, explicit overwrite and atomic final publication.
- Never send labels, role metadata, delivery notes, JSON syntax or pause annotations to synthesis. Only dialogue text is spoken. Do not strip text with broad annotation-removal regexes.
- Import, mapping and filtering must not load models, perform live voice discovery, auto-download assets or silently switch providers/fall back to Edge.

## Fixed feature decisions

The unmodified `docs/tts-sample.json` must import as version 1: three declared roles, 26 segments and 84 seconds of explicit silence. Its final 30 seconds must survive export.

Schema: absent `schema_version` means integer version 1. Speakers have `id`, `role`, optional `voice_direction`, optional `voice_defaults` mapping provider IDs to voice IDs, and optional `speech.speed`. Segments have `speaker`, `text`, optional `pause_after_seconds`, optional `voice_direction` and optional `speech.speed`.

Use case-sensitive trimmed IDs; reject surrounding whitespace rather than rewriting references. Allow duplicate display roles with distinct IDs. Preserve array order, original text and unknown extension fields. Do not coerce invalid known types.

Centralized limits: 10 MiB UTF-8 input; 10,000 segments; 1,000 speakers; explicit pause 0–600 seconds; cumulative explicit silence at most 86,400 seconds; new explicit speed 0.5–2.0. Accept finite fractional numbers; reject booleans, NaN, infinity and numeric strings. Set a documented JSON container-depth limit of 64, checked before recursive processing; reject deeper documents cleanly. Keep the existing five-second sentence/paragraph limit unchanged.

Free-text directions are notes with visible limitations. Supported structured speed is segment > role > job > provider default. Current Edge speed is unsupported: an explicit speed request must fail before synthesis. A default disabled GUI speed display is not an explicit request. No natural-language style guessing or new provider capability is required.

At JSON segment boundaries use explicit after-pauses only, without an added paragraph pause. Optional sentence pauses remain additional intra-segment pauses. A segment's after-pause occurs once after its last chunk, including the final segment. Insert `round(rate × seconds)` PCM silence frames; do not trim natural provider silence or sleep for the requested pause duration.

## Default mapping rules

Use speaker identity, provider identity and active document identity, never row position. Precedence is current user edit > explicitly loaded matching project assignment > valid imported provider default > enabled reusable role preference > deterministic provider catalog default.

For automatic defaults, rank locale match first and file presence second, prefer an unused voice among equally suitable candidates, and break ties by stable catalog order. Never infer protected or acoustic characteristics from role names. File presence is only a hint; full verification still occurs before generation in a worker.

Populate a default even when a local model is absent, label the prerequisite, and block generation for used unresolved assignments with actionable model-library guidance. Do not make unused declared local roles require an installed model. Every declared role remains visible and gets a populated assignment.

The bundled Edge catalog currently has two configured defaults. Reusing one for the sample's third role is acceptable only with a shared-voice warning. Distinct delivery cannot be claimed for repeated voice IDs. Preserve manual entry of additional Edge IDs without import-time network calls.

## Verification boundary: mandatory

The user has already completed voice testing. For this follow-up do not download or replace models, run real-model inference, make live Edge synthesis calls, generate comparative voice samples, conduct quality/listening tests, run provider benchmarks, or repeat M11 voice validation. Do not run the diagnostic/build acceptance commands if they trigger those activities. Retain the app's existing user-operated model library and preview features; test them through injected fakes.

Audit test files, `conftest`/fixtures, import-time effects and opt-in environment switches before test execution or collection. Markers alone do not establish safety. Establish an explicit allowlist of offline regression tests, new fake-provider tests, fake-provider Windows GUI tests, and synthetic FFmpeg cases. Run the permitted set, not an unreviewed bare full-suite command. Record all excluded tests and reasons separately from failures.

Fake providers must emulate both online native-MP3 and offline native-WAV contracts where relevant. Synthetic audio fixtures are programmatically generated non-speech PCM; timing/export tests are not listening or voice-quality tests. Use existing FFmpeg tools if present. Do not install missing dependencies or media tools automatically; record missing prerequisites.

Use focused checks after each change and a broad audited regression set at completion. Run changed-file Ruff checks and repository-wide Ruff checks without unrelated auto-fixes. A marker-only exclusion such as `-m 'not real_model'` is insufficient if unmarked tests or fixtures perform network/model work.

## Completion evidence

Before marking a target DONE, record:

- Implemented behavior, changed files and acceptance results.
- Exact interpreter/tool versions, safe commands and outcomes.
- Selected regression scope, excluded test IDs/files and reasons.
- Changed-file Ruff success and separate existing repository-wide findings.
- Failure/cancellation/cleanup evidence and applicable Windows UI checks.
- Manual architecture/readability review and updated documentation.
- Any missing validation; unmet required feature gates prevent DONE.

For M12–M17 the accepted fake-provider/synthetic-media verification scope replaces historical real-voice/listening requirements for this new behavior. It does not alter historical M01–M11 gates, invent a clean-machine pass, or reopen completed quality work. M10 remains independently blocked. No new feature milestone may claim real-provider or clean-machine validation from these tests.

Finish each requested milestone with a concise report: status, behavior delivered, verification evidence, exclusions, unresolved issues, and next dependency. Do not ask to repeat already authorized routine implementation work inside the requested milestone.

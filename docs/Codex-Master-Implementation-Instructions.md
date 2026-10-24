# Codex Master Implementation Instructions

## 1. Role and Mission

Act as a Principal Python Engineer, Windows Desktop Application Architect, and AI Audio Engineering Specialist.

Your responsibility is to review and improve the existing Windows Text-to-Speech application, which currently uses Python, Microsoft Edge TTS, and FFmpeg.

Implement a modular AI-powered speech generation application with support for multiple TTS providers, natural-sounding offline models, downloadable voice libraries, audio previews, text chunking, and high-quality audio exports.

**Do not rewrite the existing application unnecessarily. Preserve all working features, especially the current Edge TTS and FFmpeg workflow.**

### Primary priorities

1. Natural, human-like speech output.
2. Offline inference using CPU-only hardware.
3. Reliable and memory-efficient processing.
4. Clean, maintainable Python architecture.
5. Compatibility with existing user workflows.
6. Lightweight Windows distribution.
7. Automated tests and repeatable validation.

Use locally installed models. Do not introduce paid APIs, mandatory cloud services, or GPU dependencies.

---

## 2. Mandatory Repository Review

Before changing any code:

1. Inspect the complete repository and existing folder structure.
2. Read `main.py` and identify all existing features.
3. Identify the existing desktop framework (Tkinter, CustomTkinter, PySide6, or other).
4. Review the current Edge TTS integration.
5. Review FFmpeg installation and execution logic.
6. Identify existing text segmentation, voice selection, audio generation, progress reporting, and export behavior.
7. Inspect dependency files, packaging configuration, tests, and documentation.
8. Identify synchronous or blocking operations that could freeze the UI.
9. Identify current error handling, temporary-file cleanup, and subprocess management.
10. Document existing behavior before making architectural changes.

Do not assume any particular UI toolkit, current folder structure, or application packaging mechanism.

**Deliverable:** `docs/architecture/CURRENT_STATE.md`

Include:

- Existing features and workflows
- Current architecture
- Existing dependencies
- Performance bottlenecks
- Technical risks
- Recommended incremental changes
- Backward compatibility considerations

Do not proceed with a broad refactor until this review is complete.

---

## 3. Target Architecture

Use a provider-based architecture that makes adding future TTS engines straightforward.

Conceptual workflow:

    Desktop UI
        |
        v
    Application Service
        |
        v
    TTS Provider Registry
        |
        +-- Edge TTS Provider
        +-- Kokoro Provider
        +-- Piper Provider
        |
        v
    Text Processing Service
        |
        v
    Audio Generation Service
        |
        v
    Audio Processing / FFmpeg
        |
        v
    Preview / WAV / MP3 / M4A Export

Separate UI, model management, text processing, synthesis, and audio processing responsibilities.

### Suggested structure

Adapt the existing repository rather than forcing this structure if an equivalent architecture already exists.

    project-root/
    ├── main.py
    ├── app/
    │   ├── core/
    │   │   ├── config.py
    │   │   ├── logging_config.py
    │   │   ├── exceptions.py
    │   │   └── events.py
    │   ├── providers/
    │   │   ├── base.py
    │   │   ├── registry.py
    │   │   ├── edge_provider.py
    │   │   ├── kokoro_provider.py
    │   │   └── piper_provider.py
    │   ├── models/
    │   │   ├── manager.py
    │   │   ├── manifest.py
    │   │   └── downloader.py
    │   ├── audio/
    │   │   ├── generator.py
    │   │   ├── chunker.py
    │   │   ├── processor.py
    │   │   ├── exporter.py
    │   │   └── cache.py
    │   ├── services/
    │   │   ├── synthesis_service.py
    │   │   └── preview_service.py
    │   └── ui/
    │       └── [existing UI modules]
    ├── tests/
    ├── docs/
    │   ├── architecture/
    │   ├── milestones/
    │   └── setup/
    ├── scripts/
    ├── requirements/
    └── README.md

Model binaries and large generated audio files must not be committed to Git.

---

## 4. TTS Provider Abstraction

Create a common provider interface that supports provider discovery and speech synthesis.

All TTS providers should conform to the same contract.

### Provider capabilities

Support:

- Provider identification
- Available voices
- Supported languages
- Voice metadata
- Offline/online status
- Model availability
- Required downloads
- Supported audio configuration
- Optional features such as speaking speed
- Synthesis of a text segment
- Error reporting
- Cancellation where supported

Design the interface to avoid assuming that all providers support the same speech controls.

Suggested conceptual interface:

    TTSProvider
        provider_id
        display_name
        get_capabilities()
        get_available_voices()
        validate_configuration()
        synthesize(request, output_file, cancellation_token)

The synthesis request should include:

- Text
- Voice identifier
- Language
- Speaking rate, if supported
- Optional provider-specific settings
- Output or temporary audio format

### Edge TTS

Move the existing integration behind `EdgeTTSProvider`.

Preserve:

- Existing voices
- Existing configurable settings
- Existing text-to-audio conversion
- Existing audio merging
- Existing output formats
- Existing error-handling behavior

Do not require a local AI model to run Edge TTS.

### Kokoro

Create `KokoroTTSProvider`.

Requirements:

- CPU-only inference
- ONNX inference where feasible
- No mandatory PyTorch dependency
- Lazy initialization
- Session reuse
- Configurable voices
- Offline operation after installation
- Streaming or chunk-level progress where practical
- Predictable resource cleanup

Investigate maintained Kokoro ONNX implementations and choose one compatible with the project's Python version and packaging requirements.

### Piper

Create `PiperTTSProvider`.

Requirements:

- Local ONNX voices
- CPU inference
- Small model footprint
- Multiple voice options where available
- Efficient batch synthesis
- Configurable speaking speed where supported

Piper serves as the lightweight alternative when Kokoro is too slow for a user's CPU.

---

## 5. Model Management System

Implement a local model manager.

### Required features

- Display supported models.
- Show downloaded models.
- Download a selected model.
- Display download progress.
- Cancel supported downloads.
- Verify downloaded files.
- Prevent incomplete models from appearing installed.
- Delete unused models.
- Display model size.
- Show model and voice licensing information.
- Detect corrupted model files.
- Handle interruptions safely.
- Allow models to be installed again.
- Load models only when needed.

Use an application-specific user-data folder, such as:

    %LOCALAPPDATA%\AudioCreationApp\models\

Do not require administrator privileges.

Use a model manifest with:

- Model ID and version
- Provider ID
- Download source
- File names
- File sizes
- SHA-256 checksums
- License and attribution
- Supported voices
- Languages
- Runtime compatibility

Never load or execute a model file merely because it is found in a directory.

Use trusted download sources and verify file integrity before installation.

Support atomic installation: download to temporary files, verify all required assets, and then activate the model.

---

## 6. Natural Speech Generation

Implement natural-sounding speech generation as the primary user experience.

### Requirements

- Preserve punctuation.
- Handle sentence boundaries carefully.
- Introduce natural pauses between paragraphs.
- Support configurable speaking speed when available.
- Avoid clipping at audio boundaries.
- Avoid unnatural long silences.
- Avoid repeated or skipped text.
- Preserve audio quality across combined segments.
- Avoid abrupt volume changes.
- Preserve source language and pronunciation settings.

### Text normalization

Support safe normalization for:

- Multiple spaces and newlines
- Common punctuation
- Unicode characters
- Quotation marks
- Common abbreviations
- Numbers and dates

Do not silently change the semantic meaning of the input.

Keep original text and normalized synthesis text separate where useful.

Do not blindly expand abbreviations or numbers in ways that may produce incorrect speech.

### Chunking

Implement punctuation-aware, sentence-aware chunking.

Chunking should:

1. Prefer complete paragraphs.
2. Split paragraphs at sentence boundaries where necessary.
3. Respect provider-specific maximum input lengths.
4. Handle unusually long sentences.
5. Preserve punctuation and original text order.
6. Allow configured pauses between sentences and paragraphs.
7. Avoid duplicate or omitted speech.
8. Store chunk metadata for resumability.

Use provider-specific chunk-size limits rather than one fixed character limit for every engine.

---

## 7. Audio Preview

Implement fast audio preview for text and selected voice settings.

### Features

- Preview selected text.
- Preview a sample sentence.
- Play, stop, and replay.
- Show generation progress.
- Cancel preview.
- Cache recent previews.
- Invalidate cached previews when settings change.
- Prevent simultaneous playback conflicts.
- Keep the desktop UI responsive.

Preview should use the actual selected provider and voice, not an unrelated sample file.

Preview generation must not interfere with a running long-form export.

For expensive local inference, use a short text selection and reuse loaded model sessions where practical.

---

## 8. Audio Export Engine

Preserve the existing FFmpeg-based approach and improve its reliability.

### Formats

Support:

- WAV — lossless PCM
- MP3 — configurable bitrate
- M4A — AAC audio

Additional formats may be added later if supported reliably.

### Audio controls

- Output directory
- File name
- Format
- MP3 bitrate
- Sample rate where applicable
- Mono/stereo configuration where appropriate
- Optional loudness normalization
- Sentence and paragraph pauses

### Technical requirements

- Preserve source audio quality during intermediate processing.
- Avoid unnecessary lossy re-encoding.
- Normalize audio formats before concatenation.
- Prevent sample-rate mismatch errors.
- Use safe subprocess invocation.
- Never construct FFmpeg commands with unsafe shell concatenation.
- Handle paths containing spaces and Unicode.
- Validate the final output file.
- Remove temporary files after success or controlled failure.
- Never overwrite an existing file without appropriate user choice.

Default to a high-quality WAV intermediate workflow, applying lossy encoding only during the final export.

Do not blindly upsample generated audio or claim improved fidelity from changing sample rate.

---

## 9. Desktop UI Enhancements

Preserve the existing desktop framework unless there is a documented technical reason to change it.

Implement a modern and accessible interface with:

### Text Editor

- Large text input area
- Word and character count
- Paste and clear actions
- Optional text file import
- Paragraph-aware formatting

### Voice Selection

- Provider selector
- Voice selector
- Language/accent selection
- Voice preview action
- Offline/online indicator

### Voice Settings

- Speaking speed when supported
- Pause duration
- Output volume normalization
- Optional advanced provider settings

### Generation Panel

- Generate button
- Cancel button
- Progress bar
- Current processing status
- Chunk progress
- Elapsed time
- Output file location
- Open output folder action

### Model Library

- Installed models
- Available downloads
- Installation status
- Model sizes
- License information
- Remove model action

All intensive work must happen off the UI thread.

Use the desktop framework's safe mechanisms for updating UI state from background workers.

Do not access GUI widgets directly from arbitrary worker threads.

---

## 10. Performance and CPU Optimization

The target environment is a standard Windows 11 laptop with no dedicated GPU.

### Requirements

- Use CPU inference by default.
- Avoid downloading GPU-only packages.
- Lazy-load models.
- Reuse inference sessions.
- Load only the model needed for the selected provider.
- Limit concurrent inference jobs.
- Make ONNX thread settings configurable.
- Keep memory usage bounded during long recordings.
- Release audio buffers when no longer needed.
- Use disk-backed intermediate files where appropriate.
- Avoid loading an entire long-form recording into memory.
- Avoid repeated model initialization for every chunk.

Measure performance using real CPU inference, not mocked provider timings.

Collect:

- Model load time
- First-audio latency
- Synthesis duration
- Real-time factor
- Peak process memory
- CPU usage
- Generated audio duration
- Export time

Define real-time factor as synthesis processing time divided by generated audio duration, excluding unrelated application startup and export overhead. Report these separately.

Benchmark using multiple sample lengths and voices.

Do not promise a fixed speed without measurement.

---

## 11. Security and Licensing

Use only documented and trusted model sources.

Requirements:

- Verify downloaded model checksums.
- Avoid unsafe model deserialization.
- Prefer ONNX models with established runtime support.
- Pin and audit dependencies.
- Review licenses for inference code, model weights, individual voices, and third-party data.
- Preserve required attribution and license notices.
- Never assume all voices share the same commercial license.
- Avoid arbitrary subprocess execution.
- Handle file paths safely.
- Do not log private input text by default.
- Avoid transmitting local synthesis content to online services.
- Clearly identify Edge TTS as an online provider.
- Display the offline status of the selected engine.
- Document any relevant restrictions on distributing third-party models or voices.

Do not bundle model assets commercially until their licenses have been reviewed.

---

## 12. Automated Testing

Implement appropriate unit, integration, UI, and smoke tests.

### Unit tests

Cover:

- Provider registration
- Provider capabilities
- Invalid provider selections
- Missing models
- Model manifest validation
- Chunking
- Unicode text
- Empty input
- Abbreviation handling
- Export configuration
- Cancellation
- Error handling

### Integration tests

Cover:

- Edge TTS provider integration using controlled mocks for network operations
- Local model inference using real downloaded model assets in dedicated integration tests
- FFmpeg conversion
- Audio merging
- Preview generation
- Model installation and deletion
- Long-form synthesis
- Resume/retry behavior where implemented

### Desktop UI tests

Cover:

- Provider switching
- Voice selection
- Preview playback
- Background progress updates
- Cancellation
- Missing-model errors
- Export completion and failure

### Regression tests

Verify that all original application behavior still works.

Real-model tests should be opt-in or run in an environment with the required model assets. Unit tests must not download gigabytes of model data.

### Audio validation

Verify:

- Nonempty output
- Correct duration within reasonable bounds
- Correct format and codec
- Valid audio samples
- No unexpected leading/trailing corruption
- No duplicated chunks
- No missing chunks
- Reasonable volume consistency

A separate human listening evaluation is required for claims of naturalness. Automated file validation alone does not prove human-like voice quality.

---

## 13. Implementation Milestones

Implement these milestones sequentially.

### M01 — Baseline Review and Architecture

- Review existing implementation.
- Record existing functionality.
- Document current architecture.
- Introduce baseline regression tests.
- Define provider contracts.
- Create milestone tracker.

**Acceptance:** Baseline application still works and architecture decisions are documented.

### M02 — Provider Abstraction and Edge Migration

- Introduce provider registry.
- Create common synthesis requests and responses.
- Move Edge integration behind provider interface.
- Preserve current UI and output behavior.

**Acceptance:** Existing Edge TTS generation passes all regression tests.

### M03 — Piper Offline Provider

- Select an appropriate supported Piper implementation.
- Integrate local CPU synthesis.
- Add voice discovery.
- Implement model validation.
- Test real-model WAV generation.

**Acceptance:** A downloaded Piper voice produces valid audio with internet disabled.

### M04 — Kokoro Natural Voice Provider

- Evaluate maintained Kokoro ONNX runtimes.
- Choose a suitable CPU-compatible implementation.
- Integrate Kokoro-82M.
- Implement voice selection and lazy model loading.
- Add quality and CPU benchmarks.

**Acceptance:** Real Kokoro synthesis works offline on CPU-only Windows and produces valid audio through the existing export pipeline.

### M05 — Model Library and Download Manager

- Implement model catalog.
- Add integrity-verified downloads.
- Add installation, deletion, and recovery.
- Add model management UI.

**Acceptance:** A fresh installation can download, validate, use, and remove supported models without administrator privileges.

### M06 — Text Chunking and Natural Speech Processing

- Implement sentence-aware chunking.
- Add paragraph pauses.
- Add text normalization.
- Improve long-form generation.
- Add output metadata and chunk tracking.

**Acceptance:** Long text generates in the correct order without missing or duplicated text, and output joins are audibly acceptable.

### M07 — Voice Preview and UI Improvements

- Implement provider/voice selection UI.
- Add short previews.
- Add playback controls.
- Add progress and cancellation.
- Improve desktop responsiveness.

**Acceptance:** Users can preview voices and configure audio generation without UI freezes.

### M08 — High-Quality Export System

- Refactor FFmpeg processing.
- Support WAV, MP3, and M4A.
- Add optional normalization.
- Validate exported media.
- Improve error handling.

**Acceptance:** All supported formats produce playable files with correct metadata and no unexpected truncation.

### M09 — Performance Optimization

- Benchmark Kokoro, Piper, and Edge separately.
- Optimize CPU threads.
- Reduce memory usage.
- Improve caching.
- Optimize model lifecycle.
- Document measured results.

**Acceptance:** Real benchmark results are recorded and no unacceptable regression is introduced.

### M10 — Windows Packaging and Final QA

- Package the application for Windows.
- Include or securely locate FFmpeg.
- Keep downloadable models separate from the base installer.
- Validate a clean-machine installation.
- Complete regression tests.
- Update documentation.

**Acceptance:** A clean Windows 11 environment can install, launch, download a model, synthesize offline audio, and export playable files.

---

## 14. Milestone Execution Rules

Create the following files if they do not exist:

    docs/milestones/
        MASTER_PLAN.md
        MILESTONE_TRACKER.md
        M01_BASELINE.md
        M02_PROVIDERS.md
        M03_PIPER.md
        M04_KOKORO.md
        M05_MODEL_MANAGER.md
        M06_TEXT_PROCESSING.md
        M07_PREVIEW_UI.md
        M08_EXPORT.md
        M09_PERFORMANCE.md
        M10_PACKAGING.md

Each milestone document must contain:

- Objective
- Scope
- Dependencies
- Tasks
- Implementation constraints
- Acceptance criteria
- Test plan
- Expected deliverables
- Risks
- Completion checklist

Use these statuses:

- NOT_STARTED
- IN_PROGRESS
- BLOCKED
- DONE

A milestone may be marked DONE only after implementation, automated testing, relevant real-model validation, and documentation are complete.

Start every Codex session with [`AGENTS.md`](../AGENTS.md). The authoritative
coding conventions are [`CODING_STANDARDS.md`](CODING_STANDARDS.md). Follow
[`milestones/MASTER_PLAN.md`](milestones/MASTER_PLAN.md) and record results in
[`milestones/MILESTONE_TRACKER.md`](milestones/MILESTONE_TRACKER.md).
Every milestone must pass the coding standards completion gate: relevant Ruff
formatting and linting, automated tests, manual readability review, and current
documentation. Report pre-existing violations separately, preserve historical
statuses and completed work, and avoid unrelated bulk formatting.


Do not mark an untested feature complete.

### Execution workflow

For every milestone:

1. Read repository instructions and standards.
2. Read the master plan.
3. Read the milestone tracker.
4. Inspect relevant existing code.
5. Implement only the current milestone scope.
6. Add or update tests.
7. Run relevant tests.
8. Fix failures introduced by the milestone.
9. Validate acceptance criteria.
10. Update architecture and milestone documentation.
11. Record remaining limitations.
12. Proceed to the next milestone only when the current milestone passes its completion gate.

Preserve unrelated work.

Never delete user changes, overwrite uncommitted work, or perform destructive Git operations.

Do not commit or push automatically unless the repository instructions explicitly authorize it.

Never commit directly to `main` automatically.

If a milestone fails its gate, mark it BLOCKED with a reproducible reason rather than claiming completion.

---

## 15. Completion Report

After each milestone provide:

- Milestone ID and title
- Summary of implemented features
- Files added and modified
- Architectural decisions
- Tests executed
- Test results
- Performance measurements, where relevant
- Remaining risks
- Acceptance criteria status
- Next recommended milestone

At final completion provide a consolidated report covering:

1. All supported TTS providers.
2. Offline models and voices.
3. Audio formats.
4. Windows packaging.
5. CPU performance results.
6. Manual listening evaluation.
7. Automated test results.
8. Known limitations.
9. Installation and usage instructions.
10. Future improvement opportunities.

**Final instruction:** Favor small, reliable architectural improvements over large rewrites. Preserve Edge TTS, prioritize natural-sounding Kokoro output, retain Piper as a lightweight offline alternative, and ensure the application remains practical on Windows CPU-only hardware.
# Current Incremental Architecture

For the original pre-migration snapshot see [CURRENT_STATE.md](CURRENT_STATE.md).
The existing `ttsapp` package and Tkinter framework are retained.

```text
main.py / app.py -> gui.py -> service.py -> provider contract / registry
                              |               | Edge -> legacy tts_engine.py
                              |               | Piper -> optional CPU runtime
                              |               | Kokoro-82M -> optional CPU ONNX
                              |               v
                              |          atomic native audio_files.py
                              v
                       audio_combiner.py -> FFmpeg -> final media

gui.py -> model_library.py -> models.manager -> trusted models.catalog
                                       |             sizes, hashes, licenses
                                       v
                            user-owned verified model directories
```

The default registry contains Edge; explicit local provider instances are
injected through the service API. Unselected inference dependencies are not
imported. Catalog factories build provider descriptors using the same trusted
asset metadata as the downloader. Edge retains its atomic adapter and MP3
stream-copy path. Local engines share native WAV publication and cooperative
background-worker cleanup. FFmpeg remains separate from model inference.

Model management has no UI dependencies. The library UI sends operations to a
worker and receives typed queued progress/status events. Long-running synthesis
still uses the original main-window worker; provider switching, preview, and
UI cancellation are later milestones. User paths and licensing/runtime setup
are documented in [model library setup](../setup/MODEL_LIBRARY.md).


## M06 processed generation

`service.py` retains the default Edge path and routes offline/explicitly processed
requests through `generation.py`. `text_processing.py` preserves normalized source
spans and provider limits. Per-job directories isolate chunks; `generation.json`
records hashes/states without private source text. Shared PCM silence and FFmpeg
native decoding keep audio processing outside providers. Line progress remains
compatible and chunk progress is additive. See [setup](../setup/TEXT_PROCESSING.md).


## M07 desktop provider sessions and preview

`provider_manager.py` resolves verified installed models, reuses the selected
session, and releases unused engines. `desktop_options.py` validates immutable
worker settings outside widgets. `preview.py` synthesizes actual selected
voice/speed to an atomically published bounded PCM cache and owns native async
playback. The Tkinter class now captures controls and dispatches generation or
preview work; typed queued events render progress/results on the main thread.
Model management is modal and closes idle sessions from its worker before
modification. Graceful shutdown waits asynchronously for native cleanup.


## M08 validated export transactions

`audio_export.py` owns typed codec/rate/channel/normalization settings, lossless
common-layout preparation, final media validation, and explicit atomic output
commit. `audio_process.py` owns cancellable/timeout child lifecycles and FFprobe
JSON calls. Generic `workers.py` waits for blocking cleanup under repeated async
cancellation. The original FFmpeg adapter remains for compatibility; advanced
UI/API paths add validated WAV/MP3/M4A without moving export logic into providers.


## M09 measured CPU sessions

`providers/onnx_sessions.py` creates explicit CPU-only sessions with bounded
intra-operation threads and sequential execution. Local providers fully verify
assets on each runtime load, then reuse verified resident data. Kokoro retains
only catalog voice styles and closes the voice archive immediately after loading.
ProviderManager avoids redundant disk scans when returning the selected provider;
closing/switching or a model-library modification ends that lifetime. Explicit
Model library verification remains a full integrity check. No model quantization
or change to phonemization, speed, text chunking, or audio processing is applied.


## M10 package entry and media tools

`app.py` preserves normal Tkinter startup and adds an explicit diagnostics mode.
`runtime_paths.py` verifies hashes before adding bundled media tools to PATH;
source runs retain external tool discovery. Damaged tools receive recovery
guidance in the desktop and a nonzero JSON report in diagnostics. The diagnostics
use the same providers, model manager and validated exports as the application.
PyInstaller hooks retain native CPU/phonemizer data while excluding unselected
auxiliary weights. Builds use fresh output directories and keep user models
separate. See [Windows package setup](../setup/WINDOWS_PACKAGE.md) for the
remaining clean-machine gate and distribution obligations.


## M11 complete English voice inventory

`models/english_catalog.py` reads a bundled pinned Piper JSON snapshot and shares
Kokoro voice IDs with the installer/provider factories. The developer-only
catalog updater verifies LFS hashes and Git identities for configs/cards; no
runtime network discovery is added. Existing Kokoro/Lessac installation
identities remain compatible. ProviderManager describes every model without
loading weights; Piper validates the selected installation on first load and
switches lazily between model sessions. Numeric speaker selection is separate
from model identity, so speakers in a shared model reuse one CPU session.
Stable per-speaker IDs and catalog digests separate preview cache entries.
Desktop searches use metadata only; required-file presence is a quick hint,
while complete integrity checks and inference remain in background workers.
The library retains per-model download/removal transactions and notices.

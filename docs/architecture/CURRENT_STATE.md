# M01 Baseline: Current State

Reviewed: 2026-10-24, before introducing provider abstractions. This is a
historical baseline; subsequent decisions and changes belong in milestone notes.

## Existing features and workflows

- `main.py`: reads `conversation.txt`, parses nonblank `Speaker: text` lines,
  synthesizes in script order, prints per-line progress, then writes MP3.
- `gen_audio.py`: recombines sorted `audio_parts/line_*.mp3` without synthesis.
  This recovery helper includes every matching existing segment; unlike a fresh
  generation it cannot know which old segments belong to the current script.
- `app.py` opens `ttsapp/gui.py`, a Tkinter/ttk desktop window, version 1.0.0.
  It provides an editable multiline script, two editable speaker/voice rows,
  output file selection, Generate, per-line progress, and success/error dialogs.
- Default voices: Receptionist = `en-GB-SoniaNeural`, Caller = `en-GB-RyanNeural`.
  The service accepts other voice mappings. The GUI supplies the edited rows.
- Desktop output defaults to the user's Documents/Windows TTS App directory;
  CLI paths are relative to the working directory. Segments are kept for reuse.
- Blank lines are ignored; speaker/text whitespace is stripped. Colons inside
  dialogue and Unicode survive. Unknown speakers, missing colons, or empty
  dialogue fail validation before generation. There is no sentence chunking.
- Fresh runs combine only their current segments, preserving script order.
  A successful run atomically replaces the chosen existing output; the GUI
  offers path selection but no separate overwrite confirmation on Generate.

## Current architecture and dependencies

```text
main.py / gen_audio.py       app.py -> ttsapp/gui.py (Tkinter)
          |                                  |
          +----------- ttsapp/service.py -----+
                         |         |
                parser.py     tts_engine.py (edge_tts)
                                     |
                         audio_combiner.py (FFmpeg subprocess)
                                     |
                           MP3 files on disk
```

`gen_audio.py` directly calls the FFmpeg adapter. `config.py` holds shared
application version, voices, and default paths. No provider registry, model
manager, local inference engine, audio player, or export configuration exists.

| Dependency | Declaration | Current purpose |
| --- | --- | --- |
| Python | README: 3.10+, tested previously on 3.14 | Runtime, asyncio, pathlib |
| Tkinter/ttk | Python installation | Desktop UI and dialogs |
| edge-tts | `requirements.txt`: >=7.0 | Online Microsoft Edge synthesis |
| FFmpeg | External executable on PATH | MP3 concat with stream copy |
| pytest | `requirements-dev.txt`: >=8.0 | Offline automated regression suite |
| Ruff | `requirements-dev.txt`: >=0.9,<1.0 | Formatting and linting |
| PyInstaller | `requirements-build.txt`: >=6.11 | Windows folder distribution |

There are no mandatory GPU packages, paid APIs, or local models. Edge is online
and sends supplied dialogue text to Microsoft's service. Local providers must
never silently fall back to Edge. Existing requirements use lower bounds rather
than a reproducible lock; dependency compatibility needs verification per
provider and packaging milestone.

## Threading, errors, and resource management

The UI captures widget values on its main thread. A daemon worker runs
`asyncio.run(generate_conversation(...))`; a thread-safe queue carries messages
back to the Tkinter thread, polled every 100 ms. Generation and blocking FFmpeg
work therefore run off the GUI thread. The Generate button is disabled during
work. Closing the window does not coordinate worker shutdown or cancel FFmpeg.

The Edge adapter validates text/voice, writes to a same-directory temporary
file, checks for nonempty data, atomically replaces its destination, and removes
temporary files in `finally`. Errors retain their underlying reason. Async task
cancellation propagates and triggers cleanup. The UI has no Cancel button.

The FFmpeg adapter uses an argument list (no shell), absolute escaped concat
paths, `-nostdin`, captured errors, and `-c copy`. It writes a temporary manifest
and output, checks nonempty output, and replaces the final file only on success.
Missing FFmpeg and nonzero exits have separate actionable exceptions. There is
no timeout, cancellation handle, codec probe, or stream/sample-rate conversion.
The synchronous service call can block a caller's asyncio event loop during
FFmpeg; the current GUI isolates that event loop in its worker thread.

## Project structure and distribution

`tests/` covers parser, adapters, orchestration, and GUI helpers/worker messaging.
`docs/` contains standards, master instructions, milestone plan and tracker.
`build-windows.ps1` creates an onedir PyInstaller archive from `app.py`, checks
its file count/base library, and replaces previous generated distribution files.
FFmpeg and models are not bundled. The build currently depends on `.venv`.
Existing `audio_parts/` and `conversation.mp3` assets are tracked; preserve them,
but do not add new generated audio or model binaries to Git.

## Measured baseline and environment limitations

System Python 3.14.7 is usable. The old `.venv` launcher points to missing
`C:\Apps\Python\python.exe`; its site-packages remain available. Validation
uses system Python with process-local PYTHONPATH and ignored workspace temp
folders. No environment is deleted or replaced. FFmpeg/ffprobe were not found
on PATH during M01 inspection.

The 44 pre-existing tests pass before changes (0.55 seconds). They mock online
Edge and FFmpeg, so this does not claim a live online synthesis or actual media
playback result. New M01 baseline tests exercise CLI defaults/progress, recovery
sorting/errors, service cancellation, and validation before side effects.
See [M01 evidence](../milestones/M01_BASELINE.md) for final commands/results.

Ruff's pre-existing baseline is 26 lint violations and nine files with formatting
differences; details remain in [the adoption report](../milestones/CODING_STANDARDS_VALIDATION.md).
M01 does not reformat unrelated existing source files.

## Bottlenecks, technical risks, and incremental changes

- Each dialogue line is synthesized sequentially over the network; there is no
  sentence-aware splitting, retry, model reuse, resumability, or voice catalog.
- FFmpeg stream copy assumes compatible input streams and does not validate
  media duration or samples. Future local WAV cannot simply join Edge MP3.
- The fixed `line_NNN.mp3` names and a shared parts directory permit concurrent
  CLI/GUI runs to conflict. Job isolation should accompany future generation work.
- Existing resource cleanup is good for controlled exceptions, but abruptly
  terminating a daemon worker can leave temporary files or a subprocess running.
- No actual CPU inference performance or naturalness measurements exist; do not
  infer quality from valid files. Kokoro requires a separate listening evaluation.
- Python 3.14 wheel availability, CPU ONNX runtimes, phonemizer packaging, model
  and voice licenses, download integrity, and clean Windows installs need real
  validation. Do not promote offline providers using mocks alone.

## Architecture decisions and backward compatibility

Retain Tkinter, entry points, `ttsapp` package, parser, progress semantics,
voice defaults, MP3 default output, and atomic adapters. Define provider contracts
in [PROVIDER_CONTRACT.md](PROVIDER_CONTRACT.md), implement the registry and Edge
adapter in M02, and keep legacy `synthesize_line` callable for compatibility.
Keep FFmpeg/export logic outside providers and model lifecycle outside UI.

Proceed M01 -> M02 -> Piper M03 -> Kokoro M04 in the existing roadmap order.
Kokoro-82M is the primary natural-quality CPU target; Piper is the lightweight
fallback, and Edge remains an explicitly online option. Preserve that priority
without skipping acceptance gates. Add CPU dependencies only for the selected
optional provider; no mandatory PyTorch, cloud API, or GPU runtime.

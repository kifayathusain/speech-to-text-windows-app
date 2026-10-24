# Windows TTS App

Generates a two-voice conversation audio file from a plain-text script using
Microsoft Edge TTS, then combines the per-line audio segments into a single
file with FFmpeg. The desktop application is named **Windows TTS App**; its
version is shown in the window title and is maintained as `APP_VERSION` in
`ttsapp/config.py`.

## Prerequisites

- Python 3.10–3.13 for all providers (3.13 recommended). Edge/Piper also tested on 3.14.
- [FFmpeg and FFprobe](https://ffmpeg.org/) installed and available on `PATH`
  for source runs and packages without bundled tools.
- Internet for Edge TTS and initial model downloads. Installed local voices run
  offline on CPU; no API key or GPU is required.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# optional, for running tests:
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## Usage

### Desktop app (Windows)

```powershell
.\.venv\Scripts\python.exe app.py
```

This opens a desktop window where you can:

1. Enter or paste a conversation script, formatted as `Speaker: text` (one
   line of dialogue per line, matching `conversation.txt`'s format). Blank
   lines are ignored.
2. Edit the names and Edge TTS voices for Speaker 1 and Speaker 2. Each name
   must exactly match the corresponding label before `:` in the script; the
   default names and voices are pre-filled from `ttsapp/config.py`'s `VOICES`.
3. Choose where the combined output MP3 should be saved ("Browse...").
4. Click "Generate". The window stays responsive while Edge TTS/FFmpeg run
   in the background; progress is shown per line, and a success or error
   message is shown when done.

The desktop UI is built with Tkinter (bundled with Python), so no extra
dependency is required to run it.
By default, the final MP3 is saved to
`%USERPROFILE%\Documents\Windows TTS App\conversation.mp3`; the generated
line segments are kept in the adjacent `audio_parts` folder. Choose another
output path with "Browse..." if preferred. Existing final audio is replaced
only after a new file has been generated successfully. Temporary files are
removed automatically; only segments from the current script are combined.

### Build a distributable Windows app

Use Python 3.10–3.13 with Tkinter for the full CPU package:

```powershell
python -m venv .build-venv
.\.build-venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\build-windows.ps1 -PythonExecutable .\.build-venv\Scripts\python.exe
```

Each build creates a fresh `dist/release-*` directory and portable ZIP, preserving
previous builds. Extract the complete folder and launch `WindowsTTSApp.exe`.
The full profile includes Kokoro, Piper and Edge runtimes; model weights remain
separate downloads. Optional `-FFmpegDirectory` bundles explicitly supplied,
license-documented FFmpeg and FFprobe tools with integrity hashes; otherwise both
must be installed on PATH. See [Windows package setup](docs/setup/WINDOWS_PACKAGE.md)
for build profiles, diagnostics, licensing status and the required clean Windows
11 completion check. No release is published automatically.

### Troubleshooting

- **"FFmpeg is required" / FFmpeg not found:** Install FFmpeg, add the folder
  containing `ffmpeg.exe` to the Windows `PATH`, restart the app, and verify
  from PowerShell with `ffmpeg -version`.
- **Speech generation failed:** Confirm internet access and try again. If
  you changed a voice, verify its Edge TTS voice name; the underlying service
  error is shown in the dialog.
- **Cannot save the output:** Use "Browse..." to choose a folder where your
  Windows account has write access, such as Documents.
- **FFmpeg could not combine the audio:** Check the FFmpeg installation and
  available disk space. The dialog includes FFmpeg's error details; the
  existing final audio is preserved when combination fails.

### Command line

1. Edit `conversation.txt` with lines formatted as `Speaker: text`, one line
   of dialogue per line of the file. Blank lines are ignored.
2. Each `Speaker` label must have a configured voice in
   `ttsapp/config.py` (`VOICES`). The defaults are `Receptionist` and
   `Caller`.
3. Run the app:

   ```powershell
   .\.venv\Scripts\python.exe main.py
   ```

   This generates one MP3 per line in `audio_parts/` and combines them into
   `conversation.mp3` in the repository root.

If generation is interrupted after the per-line audio files already exist,
you can re-run just the combination step:

```powershell
.\.venv\Scripts\python.exe gen_audio.py
```

## Architecture

The application is split into a thin CLI entry point / desktop UI and a
reusable application/service layer, so neither duplicates the pipeline
logic:

```text
main.py / gen_audio.py        (CLI entry points)
app.py -> ttsapp/gui.py       (Tkinter desktop UI, M02)
         |
         v
ttsapp/service.py             (application/service layer: orchestrates the pipeline)
         |
         +--> ttsapp/parser.py         (parses "Speaker: text" script lines)
         +--> ttsapp/tts_engine.py     (Microsoft Edge TTS adapter)
         +--> ttsapp/audio_combiner.py (FFmpeg adapter)
         |
         v
filesystem/output (audio_parts/*.mp3, conversation.mp3)
```

- `ttsapp/config.py` holds shared defaults (voices, file paths).
- `ttsapp/service.py` exposes `generate_conversation(...)`, the single
  function a UI or CLI needs to call to run the full pipeline, with an
  optional progress callback. It accepts either `input_file` (CLI) or
  `input_text` (desktop UI) as the conversation script source.
- `ttsapp/tts_engine.py` validates non-empty text and voice selection, sends
  Unicode text and the selected voice to Edge TTS, and writes each segment
  through a temporary file before atomically replacing its destination. A
  failed or cancelled synthesis therefore cannot leave a partial segment in
  place; Edge TTS failures are reported with their underlying reason.
- `ttsapp/audio_combiner.py` combines segments in their parsed order using
  FFmpeg's concat demuxer. It uses temporary manifest/output files, atomically
  replaces the final audio only after successful combination, preserves any
  existing final file on failure, and reports missing FFmpeg or its error
  output clearly.
- `ttsapp/gui.py` implements the desktop window. It runs generation on a
  background thread (with its own asyncio event loop) and posts progress
  back to the UI thread through a queue, so the window never freezes while
  Edge TTS/FFmpeg are working. The validation/merging helpers
  (`validate_script_text`, `build_voice_overrides`) are plain functions kept
  separate from the Tkinter widgets so they're unit-testable without a
  display. The desktop default output goes into the user's Documents folder,
  not the current working directory, and common service failures include
  recovery guidance.

## Audio exports

The desktop supports validated WAV, MP3, and M4A with bitrate, sample-rate,
mono/stereo, optional loudness normalization, cancellation, and explicit output
replacement. Both FFmpeg and FFprobe must be on PATH for validated exports.
See [export setup](docs/setup/AUDIO_EXPORTS.md).

## Model library

Open **Model library...** to download, verify, cancel, reinstall, or remove
supported offline model files. Runtime and license details appear with each
model; Python inference dependencies are installed separately. See
[model library setup](docs/setup/MODEL_LIBRARY.md) for storage and recovery.

## Provider architecture

Generation now resolves a provider through `ttsapp/providers/registry.py`.
Microsoft Edge TTS remains the default, with the original CLI and desktop
behavior. The typed provider contract and cancellation boundaries are documented
in [the provider contract](docs/architecture/PROVIDER_CONTRACT.md).
Local model runtimes are optional and are not imported by default Edge routing.
The optional [Piper CPU provider](docs/setup/PIPER.md) is available through the
Python API with explicitly verified local voices. The [Kokoro-82M CPU provider](docs/setup/KOKORO.md) is available on Python
3.10–3.13. The desktop now includes provider selection, local voice previews, replay/stop,
progress, and cancellation; see [desktop controls](docs/setup/DESKTOP_PREVIEW.md). See the
[tracker](docs/milestones/MILESTONE_TRACKER.md) for validated status.

## Tests

Contributors and Codex sessions must start with [AGENTS.md](AGENTS.md) and follow
the authoritative [coding standards](docs/CODING_STANDARDS.md). Development
tools are installed from `requirements-dev.txt`; Ruff and pytest are configured
in `pyproject.toml`. See the [milestone plan](docs/milestones/MASTER_PLAN.md) and
[tracker](docs/milestones/MILESTONE_TRACKER.md) for scope and completion gates.

```powershell
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q
```

The automated suite covers parsing, long Unicode input, multiple voices and
segments, output-path creation, reruns/overwrites, TTS and FFmpeg failures,
cancellation cleanup, and the desktop UI's background-worker/queue boundary.
Tests mock the Edge TTS and FFmpeg adapters, so they run offline and without
requiring the `ffmpeg` executable.

For package acceptance, follow the extracted-executable and clean-machine
checks in [Windows package setup](docs/setup/WINDOWS_PACKAGE.md). An isolated
folder on the development host is useful validation but does not establish a
clean Windows 11 installation. The [tracker](docs/milestones/MILESTONE_TRACKER.md)
records which completion gates have actually passed.

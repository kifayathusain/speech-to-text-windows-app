# Windows TTS App

Generates a two-voice conversation audio file from a plain-text script using
Microsoft Edge TTS, then combines the per-line audio segments into a single
file with FFmpeg.

## Prerequisites

- Python 3.10+ (tested on 3.14).
- [FFmpeg](https://ffmpeg.org/) installed and available on `PATH` (run
  `ffmpeg -version` to confirm).
- Internet access (Edge TTS calls Microsoft's online service; no API key is
  required).

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
2. Review/override the voice used for each speaker (pre-filled from
   `ttsapp/config.py`'s `VOICES`).
3. Choose where the combined output MP3 should be saved ("Browse...").
4. Click "Generate". The window stays responsive while Edge TTS/FFmpeg run
   in the background; progress is shown per line, and a success or error
   message is shown when done.

The desktop UI is built with Tkinter (bundled with Python), so no extra
dependency is required to run it.

### Build a distributable Windows app

The app can be packaged as a self-contained, 64-bit Windows folder using
PyInstaller. The ZIP includes the application, Python runtime, and Python
dependencies; end users do not need Python installed.

From PowerShell on 64-bit Windows, run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\build-windows.ps1
```

The resulting `dist\WindowsTTSApp-windows-x64.zip` contains the app folder.
Extract the entire folder and run `WindowsTTSApp.exe`; do not move the
executable out of its folder. Builds must be produced on Windows for Windows.

FFmpeg is intentionally not bundled. Install it separately using the
[FFmpeg download options](https://ffmpeg.org/download.html) and ensure
`ffmpeg.exe` is available on `PATH` before generating audio; check with
`ffmpeg -version`. This avoids redistributing a separately licensed binary.
The app also needs internet access for Microsoft Edge TTS. Neither prerequisite
is downloaded by the app at runtime.

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
  display.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests mock the Edge TTS and FFmpeg adapters, so they run offline and without
requiring the `ffmpeg` executable. A real end-to-end smoke run (network +
FFmpeg) was performed manually during development; see
`automation/AGENT_STATE.md` for details.

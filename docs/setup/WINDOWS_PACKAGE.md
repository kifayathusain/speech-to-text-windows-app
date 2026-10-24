# Windows portable package

Extract the entire ZIP to a user-owned directory and run `WindowsTTSApp.exe`.
Keep `_internal` beside the executable. No Python installation or administrator
access is required. This local QA package has not completed clean-machine QA.

The full build includes CPU Kokoro, Piper and Edge runtimes. Model weights are
downloaded separately through Model library into `%LOCALAPPDATA%/Windows TTS
App/models`. Kokoro is the natural-quality target; Piper is lighter. Downloads
require internet; subsequent local inference requires neither internet nor GPU.
Edge always requires internet. Model and voice/data notices are separate from
runtime licenses; review them in Model library before use or redistribution.

If `tools` is included, its FFmpeg/FFprobe hashes are checked before use. Otherwise
install both tools from the build options linked at
<https://ffmpeg.org/download.html> and add their absolute `bin` directory to PATH.
Use a trusted download source and verify its published checksum. Missing tools
produce an actionable export error. The app never downloads executables itself.

## Build on Windows x64

Use a working Python 3.10–3.13 installation including Tkinter (3.13 recommended).
The build environment must be separate from user model/audio storage.

```powershell
python -m venv .build-venv
.\.build-venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\build-windows.ps1 -PythonExecutable .\.build-venv\Scripts\python.exe
```

Each invocation creates a fresh timestamped `dist/release-*` directory and ZIP;
existing builds are preserved. `-OutputDirectory` accepts another unused path.
The adjacent `.sha256` file records the ZIP digest. No model weights are bundled.
`-Profile edge` builds a smaller Edge-only runtime; install `requirements.txt`
and PyInstaller for that profile. Local choices need the full profile to run.

To bundle media tools, pass `-FFmpegDirectory C:/trusted/tools`. That directory
must contain `ffmpeg.exe`, `ffprobe.exe`, `LICENSE.txt` and `source.txt` identifying
the build source/version/checksum. The build copies notices and records binary
hashes. Bundling is explicit and introduces the chosen FFmpeg build's licensing
obligations. No download or global installation is performed by the build script.

## Required clean Windows 11 acceptance

Use a new Windows 11 VM or machine without the development checkout, Python,
model caches, or separately installed inference runtimes. Record the OS version
and package SHA-256. Install trusted FFmpeg/FFprobe if they were not bundled.

1. Extract the ZIP; launch the executable and confirm the window opens.
2. Open Model library, freshly download Kokoro-82M and Piper Lessac, and Verify.
3. Disconnect networking. Preview both local providers, stop/replay, generate a
   multi-speaker script, and export WAV, MP3 and M4A. Play the outputs and check
   sentence joins. Confirm cancel and close do not leave a running process.
4. Reconnect. Generate with Microsoft Edge TTS and confirm playable output.
5. Reopen the app and verify models persist outside the extracted package.

For an additional repeatable report, use an empty output directory:

```powershell
$app = Start-Process .\WindowsTTSApp.exe -ArgumentList '--diagnostics C:/tts-qa/report --check-edge' -Wait -PassThru
$app.ExitCode
```

The diagnostics use installed models and fixed public sample text. They do not
download unless explicitly passed `--download-model kokoro-82m-v1` and/or
`--download-model piper-lessac-low`. `--model-root` selects an isolated managed
model library. The JSON report validates real runtime loads, all three formats,
codecs and duration, but cannot establish a clean host or replace UI/listening
checks. Keep `acceptance.json`, notes and the ZIP hash for the completion gate.

## Distribution status

This is an unpublished local QA artifact. Dependency metadata and available
license texts are retained under `licenses/`. Full builds include GPL components
(Piper, phonemizer, eSpeak); application-license compatibility and complete
corresponding source/build materials must be resolved before public distribution.
The project has not automatically been assigned or changed to a new license.
The executable is not application-code-signed; do not disable Windows security
controls to run it. Record any security-policy block as a QA failure.

# Windows TTS implementation status

Updated 2026-10-25. [Milestone tracker](milestones/MILESTONE_TRACKER.md) is the
source of truth: **M01-M09 DONE; M10 BLOCKED on clean Windows 11 QA**. The user
confirmed that a clean machine is unavailable. No completion claim is made for
that gate. Start Codex sessions with [AGENTS.md](../AGENTS.md) and follow the
[authoritative standards](CODING_STANDARDS.md).

## Supported providers and models

| Provider | Runtime | Catalog voices | Connectivity |
| --- | --- | --- | --- |
| Kokoro-82M | Full precision ONNX, CPU, Python 3.10-3.13 | af_heart, af_bella, am_adam, bf_emma | Initial model download; inference offline |
| Piper | Piper 1.8.0/ONNX CPU | en_US-lessac-low, 16 kHz mono | Initial voice download; inference offline |
| Microsoft Edge TTS | Existing asynchronous Edge adapter | Existing Sonia/Ryan defaults and explicit Edge voice IDs | Online service, no API key |

Kokoro is the natural-quality CPU target; Piper is the lightweight alternative.
No GPU, mandatory paid cloud API, PyTorch or application rewrite was introduced.
Model library provides versioned HTTPS downloads, sizes, full hashes, notices,
cancel, Verify, reinstall/remove, staging recovery and atomic activation.
Provider sessions load lazily and are released on switching/library modification.
See [architecture](architecture/ARCHITECTURE.md), [Kokoro](setup/KOKORO.md),
[Piper](setup/PIPER.md) and [model library](setup/MODEL_LIBRARY.md).

## Preserved and added application behavior

The Tkinter desktop, `main.py`/`gen_audio.py` CLI entry points, default Edge voices,
script parsing and service boundary remain. The desktop adds provider/language/
voice selection, real preview/replay/stop, speed, counts, progress, cancellation
and graceful cleanup. Conservative text chunking retains normalized source
coverage and configured sentence/paragraph pauses. Per-job disk-backed chunks
and privacy-conscious metadata isolate concurrent/failed jobs.

Validated exports support PCM WAV, MP3 and AAC M4A, common sample rate/channels,
bitrate controls, optional two-pass loudness normalization, explicit replacement,
subprocess cancellation/timeouts, complete decode checks and atomic publication.
FFmpeg processing remains separate from synthesis. The legacy no-settings path
is preserved. See [desktop](setup/DESKTOP_PREVIEW.md),
[text processing](setup/TEXT_PROCESSING.md) and [exports](setup/AUDIO_EXPORTS.md).

## Windows artifact and remaining gate

Local full QA ZIP: `dist/m10-qa-03/WindowsTTSApp-windows-x64.zip`, 148,750,055 bytes.
SHA-256: `1d6c0ecda880f45eb38c0727164b37373110cc479b7b0a028d4946abca68f53f`.
It includes Python/Tk, CPU runtimes and explicit FFmpeg/FFprobe tools with hashes,
but no model weights or GPU binaries. Extract the entire folder and launch
`WindowsTTSApp.exe`; no Python installation is required. Builds preserve earlier
artifacts and never commit, push or publish.

Real fresh-download validation on the development host passed for both models.
The final extracted archive passes real Kokoro, Piper and Edge synthesis and all
nine provider/container export combinations. Desktop startup, model-library UI,
local voice controls, missing-model guidance and graceful closure were inspected.
[Package evidence](performance/M10_PACKAGE_ACCEPTANCE.json) distinguishes each
build and does not claim a clean OS.

[Windows package setup](setup/WINDOWS_PACKAGE.md) gives build/install instructions
and the required separate clean Windows 11 checklist: fresh downloads, offline
local preview/synthesis/playback, all formats, Edge after reconnecting, cancel/
close and persistent models. Windows Sandbox is unavailable here; the user also
has no clean machine. M10 stays BLOCKED. The app executable is unsigned and no
security setting was bypassed. This is an unpublished local QA artifact; GPL
compatibility/corresponding-source requirements remain open before distribution.

## CPU results and listening

On an Intel i5-1235U Windows laptop, final full Kokoro median RTF was 1.615 and
peak working set 592.4 MiB at four threads without the memory arena. Piper's
four-thread arena-enabled median RTF was 0.088, with first completion 5.49s
versus the original 3.54s; warm throughput is favored over one-time startup.
Edge's four real online samples measured median RTF 0.484. These are small-sample
observations, not guarantees across hardware, texts or networks. Full weights
remain unchanged. [M09 measurements](performance/M09_PERFORMANCE.md) record
thread/arena comparisons, raw CPU/memory/export metrics and explicit tradeoffs.

M06's actual Kokoro join sample was accepted by the user: “The joins sound
acceptable.” This validates the reviewed joins, not a general naturalness score
or the missing clean-machine playback check.

## Verification and known limitations

- Final regression suite: **212 passed, nine explicit opt-in skips**. Real
  FFmpeg export/decode and native playback checks were enabled.
- Real local provider/preview/integrity subset: **38 passed**. Windows Tkinter/
  Piper UI/export checks: two passed; playback passed separately in the full run.
- Extracted-executable fresh model download/use check: one passed. The final
  extracted build also returned exit 0 for all three real providers and formats.
- Changed Python files pass Ruff lint/format and manual readability review.
  Documentation links/fences, all ten milestone templates, TOML and the
  PowerShell build script were validated.
- Pre-existing lint: two I001 import findings in `main.py` and
  `tests/test_parser.py`. Pre-existing formatting: those two files plus
  `gen_audio.py`, `tests/test_audio_combiner.py`, `tests/test_tts_engine.py`.
  No unrelated formatter changes or lint suppressions were applied.
- Original `.venv` refers to a missing Python installation and was preserved.
  Tests/build used documented isolated working interpreters. Kokoro currently
  requires Python below 3.14; a full portable build supplies supported Python.
- Native inference cancellation is cooperative and waits for the current
  inference boundary/cleanup. Objective audio metrics do not replace listening.

Next action is the blocked M10 clean-machine gate. After that, broader hardware
benchmarks and additional vetted voices are possible improvements; neither
changes the current acceptance requirements or authorizes automatic publication.

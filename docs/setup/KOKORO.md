# Optional Kokoro-82M CPU Setup

Kokoro-82M is the natural-quality target. Piper remains the lightweight offline
alternative; Edge remains available without local models. No naturalness claim
is established by automated validation; human listening is a separate check.

## Supported runtime

Use a supported Python 3.10–3.13 installation with `requirements.txt`,
`requirements-dev.txt` for tests, and optional `requirements-kokoro.txt`.
The selected [kokoro-onnx 0.6.1 package](https://pypi.org/project/kokoro-onnx/0.6.1/)
requires Python <3.14. Edge and Piper remain usable on the existing Python 3.14;
this narrower requirement applies only to the Kokoro profile. Package code is
MIT-licensed; the [Kokoro-82M weights](https://huggingface.co/hexgrad/Kokoro-82M)
are identified upstream as Apache-2.0. Preserve applicable voice/data notices,
including the upstream model card's dataset attributions, before distribution.

Use the CPU package, not the GPU extra or PyTorch-based Kokoro implementation.
The provider creates `CPUExecutionProvider` explicitly, disables ONNX Runtime
telemetry, and uses configurable intra-op CPU threads (default two). Model files
and the bundled eSpeak resources are used locally; no implicit downloads or
online fallback occur. Inference libraries are imported only when selected.

M04 validation used signed official Python 3.13.17. The initially attempted
uv-managed runtime was blocked by Windows Application Control for unsigned
`_overlapped`; the official signed distribution worked without changing system
security settings. Production setup should use a complete official Python
installation; the minimal embeddable validation environment is not a desktop
installer or a packaging acceptance result.

## Verified assets

Download the unquantized model and voice archive from the pinned
[upstream model-files-v1.1 release](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1)
into an explicit user-owned directory. No assets are bundled with this code.

| Asset | Bytes | SHA-256 |
| --- | --- | --- |
| [kokoro-v1.0.onnx](https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx) | 325,505,369 | `beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a` |
| [voices-v1.0.bin](https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin) | 28,214,398 | `bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d` |

Both digests were verified against the release API metadata before loading.
This is the full v1.0 ONNX export of Kokoro-82M, not the int8/fp16 variant.
The initial catalog exposes af_heart, af_bella, am_adam (US English) and bf_emma
(British English). Only explicitly configured voice metadata is advertised;
loading checks that catalog voices actually exist in the verified archive.

## Python API

Use `kokoro_v1_model(directory)` from `ttsapp.models.kokoro_catalog` to create
its explicit descriptor, then `KokoroTTSProvider(model, cpu_threads=4)`. Pass
`provider_id="kokoro"` and that instance to `generate_conversation`, with speaker
voice IDs such as `af_heart` and `bf_emma`. Existing Edge defaults are unchanged.
`get_available_voices()` needs no model loading. Call `close()` after generation,
outside the UI thread; it releases the resident styles and model session.

The provider generates native 24 kHz mono PCM16 WAV. The validated export API supports
MP3, PCM WAV, and M4A with FFmpeg; no renaming of WAV bytes to MP3 occurs. Model assets
are fully verified before every model load. Verified weights and catalog voice
styles stay resident for warm requests; the archive is closed after loading.
Inference is serialized off the event loop,
and output publication is atomic. Requests are limited to 2,000 characters to
bound per-segment audio memory. The service automatically chunks long inputs within provider limits;
direct provider requests must remain below that bound. Speed range is 0.5–2.0.

Cancellation is cooperative before/after a native inference call and before
publication; native execution is allowed to finish and clean up before a
cancelled awaiter returns. No forced native-thread termination is attempted.
Desktop voice switching and preview are available alongside the Python API.

## Tests and benchmarks

Set `TTS_KOKORO_MODEL_DIR` to the verified asset directory and ensure FFmpeg is
on PATH, then run `python -m pytest -q tests/test_kokoro_integration.py`. The test
uses actual CPU inference with Python DNS/connection helpers blocked, verifies
PCM output, generates multiple voices using one session, and decodes the final
MP3 with real FFmpeg. It does not disable the OS network adapter.

For repeatable local measurements install optional `requirements-benchmark.txt`:

```powershell
python -m scripts.benchmark_kokoro --model-dir C:/path/to/kokoro --output-dir C:/path/to/results --cpu-threads 2
```

The report records model verification/load time, first completed audio latency,
per-request synthesis time, audio duration, real-time factor, CPU time, memory,
PCM peak/RMS/clipping fraction, and export time for two voices and two lengths.
Synthesis timing includes request validation and PCM writing, but excludes
initial loading and export. Warm requests reuse verified resident data. Process CPU percentage may exceed 100% for parallel
threads; peak working set is cumulative for the process. Objective waveform
checks do not replace human listening or establish speech naturalness.

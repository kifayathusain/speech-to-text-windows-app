# Optional Piper CPU Setup

Piper is the lightweight offline alternative. Kokoro-82M remains the primary
natural-quality target. Edge continues to work without installing Piper.
The desktop provider selector and preview are available; the Python API remains supported.

## Runtime and model sources

Install `requirements.txt` and optional `requirements-piper.txt` into a working
Python environment. Piper 1.8.0 was selected from the maintained
[OHF project](https://github.com/OHF-Voice/piper1-gpl), using its
[documented Python API](https://github.com/OHF-Voice/piper1-gpl/blob/v1.8.0/docs/API_PYTHON.md).
The [published release](https://pypi.org/project/piper-tts/1.8.0/) supplies a
Windows x64 stable-ABI wheel. Application calls explicitly select CPU inference.
No GPU, PyTorch, HTTP server, or cloud API is installed or required.

Runtime license: GPL-3.0-or-later, as identified by the release metadata. Model
and voice/data licenses are separate. Review them before distribution; no models
or optional runtimes are bundled by this milestone.

The initial explicit catalog descriptor is `en_US-lessac-low`, mono 16 kHz.
Its [model card](https://huggingface.co/rhasspy/piper-voices/blob/5041a7a49ae5b3a0f30e6837769eb03fdbb231bd/en/en_US/lessac/low/MODEL_CARD)
links to the [Lessac dataset terms](https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/license.html).
Do not assume the repository-level license covers every voice. This low-quality
voice demonstrates functionality and is not a naturalness/quality claim.

## Explicit asset installation

Use Model library for managed installation. For explicit API setup, download
these two files from pinned
upstream revision `5041a7a49ae5b3a0f30e6837769eb03fdbb231bd` into a user-owned model
directory. Retain the model card and relevant license information alongside them.
The provider never silently downloads or scans unknown models.

- [en_US-lessac-low.onnx](https://huggingface.co/rhasspy/piper-voices/resolve/5041a7a49ae5b3a0f30e6837769eb03fdbb231bd/en/en_US/lessac/low/en_US-lessac-low.onnx)
- [en_US-lessac-low.onnx.json](https://huggingface.co/rhasspy/piper-voices/resolve/5041a7a49ae5b3a0f30e6837769eb03fdbb231bd/en/en_US/lessac/low/en_US-lessac-low.onnx.json)

| File | Bytes | SHA-256 |
| --- | --- | --- |
| Model | 63,201,294 | `f7d01dde371555732c4c314111ac79672b1a5ce2fc19266ab42178fd8df7f375` |
| Config | 4,882 | `45754dfdebb3b8661c3fc564713772deec6e064feeb5b4e9594857dc7305193a` |

The model hash was verified against upstream LFS metadata. The configuration's
Git blob identity was verified at the pinned revision, then SHA-256 recorded.
The provider validates both files before inference. Further voices require
explicit `PiperModel` descriptors with their own trusted checksums/metadata.
Only bundled eSpeak phonemization is currently supported, avoiding optional
language-resource downloads. English/other eSpeak languages retain their voice
configurations; no unsupported external phonemizer is silently selected.

## Python API

```python
import asyncio
from pathlib import Path

from ttsapp.models.piper_catalog import lessac_low_model
from ttsapp.providers.piper import PiperTTSProvider
from ttsapp.service import generate_conversation

model = lessac_low_model(Path("C:/Users/your-name/AppData/Local/Windows TTS App/models/piper"))
provider = PiperTTSProvider((model,))
try:
    asyncio.run(
        generate_conversation(
            input_text="Narrator: Hello from the offline voice.",
            voices={"Narrator": model.voice.voice_id},
            provider_id="piper",
            provider=provider,
            output_dir=Path("audio_parts"),
            final_audio=Path("conversation.mp3"),
        )
    )
finally:
    provider.close()
```

FFmpeg on PATH is required for the final MP3/WAV export. Piper itself generates
native WAV without FFmpeg. The provider reuses one loaded voice session, keeps
inference off the event loop, serializes jobs, checks cooperative cancellation
between generated chunks and before publication, and releases its session on
`close()`. Running native inference cannot be forcibly interrupted mid-sentence;
cancellation waits for that boundary and cleanup. Calling `close()` waits for
any running job, so perform it outside the UI thread.

The validated export API supports WAV, MP3, and M4A with common-rate/channel
normalization. The compatibility path without export settings retains its
original MP3/PCM WAV behavior. See [audio exports](AUDIO_EXPORTS.md).

## Verification

Ordinary unit tests need no model/runtime downloads. Opt into the real test with
`TTS_PIPER_MODEL_DIR` pointing to verified assets and FFmpeg on PATH:

```powershell
$env:TTS_PIPER_MODEL_DIR = "C:/path/to/piper-assets"
python -m pytest -q tests/test_piper_integration.py
```

The test blocks Python DNS/network connection helpers, verifies an actual CPU
session and nonzero PCM samples, synthesizes a two-line conversation, decodes
the exported MP3 with real FFmpeg, and compares its duration with the source
segments. This does not disable the machine's network adapter or prove voice
naturalness; it verifies local inference with Python network access denied.

## CPU session settings

The provider defaults to four intra-operation threads and one sequential
CPU session. Pass `cpu_threads=1`, `2`, or `4` to `PiperTTSProvider` when measuring
your hardware. `memory_arena` is an advanced constructor setting; the measured
default is documented in [M09 performance](../performance/M09_PERFORMANCE.md).
No GPU execution provider is enabled. Every model load verifies full asset hashes;
warm requests reuse verified resident weights. Closing or switching a session
forces verification again on its next load. Model library Verify always reads
the actual files.

# Validated Audio Exports

The desktop Audio export panel supports PCM WAV, MP3, and M4A/AAC. Choose the
file, format, optional MP3 bitrate, sample rate/channels, and loudness
normalization. Existing destinations require an explicit Replace choice.
Cancellation/timeout terminates and reaps the current FFmpeg/FFprobe process;
failed or cancelled work preserves the previous final file.

Install the complete FFmpeg toolset so **both `ffmpeg` and `ffprobe` are on PATH**.
The validated desktop/export API uses FFprobe for actual JSON codec/container,
rate/channel, and duration checks, then fully decodes final media with FFmpeg.
The original CLI/service path without `export_settings` remains compatible with
its prior FFmpeg-only workflow and atomic output behavior.

## Defaults and quality

Compatible MP3 input is stream-copied when no bitrate, resampling, channel, or
normalization change is requested. This preserves the existing Edge MP3 path
without an unnecessary lossy re-encode. Other processing uses disk-backed PCM16
WAV intermediates and applies lossy encoding only for the final MP3/AAC output.

Native rate/source layout chooses the highest source rate/channel count when
segments differ, rather than dropping detail from the higher-rate source.
Lower-rate segments are converted only to establish the required common layout;
no added fidelity is claimed. Explicit rate/channel controls override that
choice. Mono/stereo changes are intentional; duplicating mono does not create a
new stereo recording.

MP3 Auto uses stream copy where possible, otherwise 160 kbps below 32 kHz and
192 kbps at higher native rates. Explicit choices range from 64 to 320 kbps.
MPEG-2 MP3 at native 16/22.05/24 kHz cannot use bitrates above 160 kbps; choose an
explicit rate of at least 32 kHz for higher bitrates. Invalid combinations fail
rather than being silently clamped or automatically upsampled. WAV is PCM16;
M4A uses AAC in an MP4-family container.

Optional normalization measures the complete recording, then applies a two-pass
`loudnorm` filter targeting -16 LUFS, 11 LU range, and -1.5 dB true peak. Output
rate is explicitly set so the filter does not accidentally leave a 192 kHz
output. Silent/non-finite loudness measurements fail clearly. These controls
follow the [official FFmpeg filter documentation](https://ffmpeg.org/ffmpeg-filters.html#loudnorm);
codec/container metadata follows the [FFprobe JSON interface](https://ffmpeg.org/ffprobe.html).

## Atomic validation and API

Every advanced export validates actual codec/container, rate, channels, explicit
MP3 bitrate, duration within 0.25 seconds, and complete decode before publishing.
Temporary files stay beside the destination for same-filesystem atomic commit.
The non-overwrite commit also refuses a file created by another job after the
initial existence check. Post-commit cleanup failures are logged as warnings;
valid completed audio is not misreported as a failed/rolled-back export.

```python
from ttsapp.audio_export import ExportSettings

# Pass to generate_conversation(..., export_settings=settings).
settings = ExportSettings(
    audio_format="m4a",
    normalize=True,
    overwrite=False,
)
```

The service accepts optional `on_export_progress(stage)` for preparation,
normalization, encoding, and validation status. The desktop displays these stages
with responsive cancellation and elapsed time. Background work waits for cleanup
even when its async task receives repeated cancellation. Default per-process
timeout is 600 seconds, configurable through `ExportSettings`.

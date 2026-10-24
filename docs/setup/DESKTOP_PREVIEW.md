# Provider Selection and Voice Preview

The existing Tkinter conversation workflow remains: enter `Speaker: text`, map
speaker names to voices, select an output file, and Generate. Edge remains the
default and keeps its editable voice IDs and original processing behavior.

The provider selector offers Edge (online), Kokoro-82M (offline CPU quality
target), and Piper (offline lightweight). The status identifies online/offline
operation and runtime prerequisites. Offline voices come from the verified model
catalog. The language/accent control filters the available voice choices;
explicit speaker voice selections determine synthesis. Speaker names and each
provider's last voice choices are retained when switching.

Install optional runtime dependencies and models as described in
[Kokoro](KOKORO.md), [Piper](PIPER.md), and [model library](MODEL_LIBRARY.md).
Kokoro requires Python 3.10–3.13; selecting it on the existing Python 3.14 reports
a prerequisite error rather than sending text to Edge. Only the selected model
session is retained; switching engines releases the previous one.

Each speaker has a **Preview** button. Select text in the editor to preview it
with that row's voice, or leave no selection to generate a short sample. Known
speaker labels are removed; ordinary colons/dates remain. Previews use up to
400 characters and the selected speaking speed. **Play / Replay** replays the
last valid preview; **Stop** stops playback. **Cancel** cancels preview generation
or export work. Playback uses asynchronous native Windows PCM audio.

Preview cache keys include actual text, provider/model asset identity, voice,
and speed. Changing provider/voice/speed invalidates the current replay selection;
late results from old settings are ignored. The disk cache holds up to eight
verified WAV files under the app's user-data `previews` directory, without
writing private source text to filenames or ordinary logs. Failed/cancelled
previews clean temporary data and preserve earlier valid cached previews.

Preview generation and export are serialized by the UI so they do not compete
for an inference session or playback. Generate stops current playback. The model
library is modal, and model modification releases idle inference resources from
its worker before replacing/removing files. Closing the app cancels active work,
keeps the event loop responsive during cleanup, and unloads retained sessions.
Native inference cancellation waits for its current execution boundary.

Speed controls are enabled only for supported offline engines. Processed text
and configurable pauses are automatic for offline engines and opt-in for Edge,
so existing Edge defaults remain intact. Word/character counts, Paste/Clear,
chunk progress, elapsed time, output browsing, and Open folder are available.
Validated WAV/MP3/M4A controls are available; see [audio exports](AUDIO_EXPORTS.md).

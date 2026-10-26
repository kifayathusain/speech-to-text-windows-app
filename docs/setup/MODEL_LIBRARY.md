# Offline Model Library

Open **Model library...** from the desktop application. The catalog lists
Kokoro-82M first as the quality target and Piper Lessac low as the lightweight
default, followed by all pinned British/American Piper model variants, with
download size, voices, languages, runtime prerequisites, and
license/attribution information. **License information** opens the selected
upstream license/model notice page. Installing model files does not install a
Python runtime or optional inference packages; see [Kokoro](KOKORO.md) and
[Piper](PIPER.md) setup. Use the desktop provider selector after installing the runtime and model.

**Download / Reinstall** fetches every required asset, checks expected sizes and
SHA-256, and activates the directory only after complete verification. **Cancel**
requests cleanup; a blocked network read may take up to its 30-second timeout.
**Verify** checks known installed files for corruption. **Remove** confirms the
selected deletion and preserves other models/directories. Close active inference
before removing a model whose files are in use.

Default storage is `%LOCALAPPDATA%\Windows TTS App\models`, with a user-home
fallback when LOCALAPPDATA is unavailable. Administrator privileges are not
required. The manager creates no user directories merely by importing modules
or listing the catalog. Installations contain an `installed.json` manifest with
model/version/provider, file integrity data, runtime, voice/language, and
license/attribution metadata. It never loads arbitrary models found on disk.

Downloads occur in private staging directories. Same-model operations use an OS
file lock; incomplete downloads never appear installed. Controlled failure or
cancellation removes staging and preserves the previous installation. A later
installation cleans interrupted staging and restores a verified backup when
activation was interrupted. Invalid backups are preserved until a new verified
installation succeeds. All deletion/move targets are checked inside the intended
model root; manifests reject unsafe IDs, filenames, and untrusted download URLs.

The Tkinter window performs networking, hashing, activation, and removal in a
background worker and renders queued results only on the main UI thread. Closing
the library requests cancellation and waits asynchronously for cleanup. Abrupt
process termination can leave recoverable staging; it cannot make partial assets
appear installed. No model binaries are included in Git or automatically bundled.


## Complete English library (M11)

The bundled offline inventory includes 28 Kokoro voices and 38 Piper English
model variants (2,006 individual speaker choices). Search the library by model
name or quality and scroll to the desired entry. Large multispeaker models are
installed once for all their speakers. Downloads remain explicit and per model.
The main window supports voice-name, quality and upstream-speaker-name search
with en-US/en-GB filtering. Filtering does not change existing selections.
Selected voice details show its model ID and whether required files are present;
full integrity and installation checks run in workers before use. Reopen the
library to verify or reinstall a corrupt model. Each model retains its own card
and license link; no shared voice license is assumed.

Existing Kokoro and Lessac low installation identities and asset hashes are
preserved. No model weights are downloaded at startup. Future inventory updates
require a reviewed metadata snapshot; see [M11](../milestones/M11_ENGLISH_VOICES.md).

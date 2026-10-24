# Offline Model Library

Open **Model library...** from the desktop application. The catalog lists
Kokoro-82M first as the quality target and Piper Lessac low as the lightweight
alternative, with download size, voices, languages, runtime prerequisites, and
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

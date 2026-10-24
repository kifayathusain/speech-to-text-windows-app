# Provider Contract and Incremental Migration Decision

M01 defines this contract; M02 implements it without changing existing CLI/UI
calls or moving working adapters unnecessarily.

## Data and capabilities

Use immutable typed records for voice metadata, provider capabilities, synthesis
requests, and results. A voice has provider-local identifier, display name,
language, optional model identifier, and license metadata when known. A provider
has stable ID/display name, online/offline status, supported native formats and
controls, cancellation capability, and model/download requirements. Do not
advertise speaking rate, format, or cancellation support that is not implemented.

A synthesis request contains text, voice ID, optional language, optional speed,
and native audio format. Add typed provider-specific settings only when needed;
do not make a universal unvalidated options dictionary. Results contain the
completed destination and actual native format, never a partially written file.

## Provider operations

- `get_capabilities()` returns metadata without loading inference models.
- `get_available_voices()` returns known voices without silently downloading.
- `validate_configuration(request)` rejects invalid text, unsupported controls,
  unknown local voices, missing/incompatible models, and unavailable formats.
- `await synthesize(request, output_file, cancellation_token)` writes complete
  native audio, returns a typed result, or raises an actionable exception.
- Model sessions are initialized lazily and reused. Add explicit lifecycle
  cleanup when local sessions require it; providers never access UI widgets.

The registry rejects empty/duplicate IDs and unknown selection with descriptive
errors. Default selection is Edge for backward compatibility. Provider lookup
must not import or initialize unselected offline runtimes. No local provider
falls back to online synthesis, downloads weights, or executes arbitrary model
assets merely because a path exists.

## Cancellation and output safety

A cancellation token uses a thread-safe signal. Check before starting and before
publishing output. Async task cancellation must propagate, not become a generic
synthesis error. Edge's existing temporary-write/atomic-replace adapter remains
the owner of its output safety. In-flight Edge work can be cancelled as an
async task; blocking local inference must expose honest cooperative boundaries.
Cancellation must clean incomplete files and preserve previously valid output.
Completed per-line segments remain available as in the original recovery flow.

## Service and export boundary

`generate_conversation` gains optional provider selection/injection after its
existing parameters. Omitted selection preserves default Edge behavior and
existing monkeypatchable adapter calls. A generation resolves one provider and
uses it for all segments. Preserve existing `ConversationLine` progress callbacks.

Synthesis produces its declared native format. The FFmpeg adapter remains the
single owner of concatenation and encoding. Edge MP3 continues the existing
stream-copy path. Local WAV needs explicit conversion to the selected final
format, not a renamed extension or mixed-codec concatenation. Extend audio
conversion only in the milestone requiring it, with real FFmpeg validation.

## Errors, tests, and extension constraints

Keep existing Edge/FFmpeg exception behavior. Provider-selection/configuration
errors must be actionable and occur before output side effects. Test registry
errors, metadata, unsupported controls, default Edge routing, explicit injection,
Unicode, errors, cancellation, atomic output, and legacy CLI/UI regressions.
Piper/Kokoro require separate real-model offline tests before DONE; neither a
mocked adapter nor a nonempty dummy file proves CPU synthesis works.


## M02 implementation record

Implemented in `ttsapp/providers/base.py`, `registry.py`, and `edge.py`.
`create_default_registry()` registers Edge only, importing no local runtime.
The service supports keyword-only `provider_id`, `provider`, and
`cancellation_token`; injected provider IDs must match the selected ID.
Existing positional arguments and no-token adapter calls are preserved.
All requests are validated before output directories are created. Native MP3
remains the sole supported service format until M03's tested WAV conversion.
See [M02 evidence](../milestones/M02_PROVIDERS.md).


## M03 native audio and model validation

Piper supplies native PCM WAV from explicit, checksum-verified `PiperModel`
descriptors. `lessac_low_model(directory)` describes the pinned initial voice;
no arbitrary asset scanning or automatic download occurs. Register/inject a
configured provider explicitly; the default registry still contains Edge only.
The service chooses native MP3 when supported, otherwise native WAV. FFmpeg
encodes WAV to final MP3/PCM WAV and rejects mismatched WAV segment layouts.
Piper reuses one CPU session, serializes background inference, cleans temporary
files on cancellation/failure, and exposes `close()` to release the session.
See [setup](../setup/PIPER.md) and [M03 evidence](../milestones/M03_PIPER.md).

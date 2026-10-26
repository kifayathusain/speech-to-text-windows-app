# M14 — Structured generation and exact segment pauses

Initial status: NOT_STARTED. Dependency: M13 DONE. Read shared rules before editing.

## Objective

Generate structured conversations through the existing service with correct voices, effective settings, chunk order and explicit silence, preserving legacy generation behavior.

## Implementation tasks

1. Add a keyword-only typed-document input to `generate_conversation` or a small service wrapper. Reject simultaneous explicit document/text sources. Preserve text-over-default-file behavior and all existing positional calls; document how explicit file inputs select their format.
2. Complete document/mapping/settings/output validation before any synthesis or job-file creation. Asset checks remain in workers. Preflight all used voices/configurations so a later segment's invalid settings do not cause partial synthesis.
3. Extend the resolved/chunk representation additively. Preserve segment identity, speaker, full voice ID, effective speed and normalized source span through each chunk. Never merge across source segments or setting changes.
4. Build ordered speech and silence items. Insert optional sentence pauses only inside a segment; insert each explicit after-pause exactly once after its last speech chunk, including the last segment. Do not add implicit paragraph silence at JSON boundaries.
5. Route JSON through processed generation, including Edge. Retain native MP3 Edge synthesis and decode once into the existing PCM path; preserve the legacy unprocessed Edge fast path for legacy requests.
6. Reuse streaming cancellable silence writing. Match source PCM layout or prepare it through the existing exporter. Do not hold a 600-second buffer or sleep in real time. Keep legacy text pause bounds unchanged.
7. Pass effective speed separately for every speech chunk using the existing provider request. Preserve one-provider sessions, lazy Piper model switching and full stable voice IDs.
8. Reuse WAV/MP3/M4A export, layout conversion, normalization, overwrite checks, timeout/cancellation and atomic output publication. Make no broad audio-module changes unless a concrete test exposes a gap.
9. Extend/version `generation.json` for resolved segment identity, timeline item order, settings, assignment hashes and silence durations/states. Include changes in pauses, mappings and applied speed in request identity. Hash private notes/text in diagnostics. Do not implement implicit chunk reuse/resume.
10. Preserve old per-line progress callback shape, adapting resolved segments as needed; report a segment complete after its planned speech and after-pause are materialized. Additive chunk/stage events may give finer detail. Keep progress monotonic and failures/cancellation correctly recorded.
11. Check cancellation during inference, decoding, silence writing and export, including task cancellation while a blocking worker is cleaning up. Preserve completed parts as existing behavior allows and remove incomplete temporary files.

## Required acceptance

- Fake synthesis sees only source dialogue chunks with the intended voice/speed; no metadata becomes speech.
- Reassembled normalized chunks cover each source segment exactly once and in order.
- Sample timeline has 26 segment after-pauses totaling 84 seconds, including the trailing 30 seconds; chunk count may exceed 26 without duplicating pauses.
- Zero adds no silence; fractional/long pauses have `round(rate × seconds)` frames; final silence survives PCM joining and exports.
- Optional sentence pauses add only their documented intra-segment silence. JSON paragraph whitespace adds no extra segment-boundary pause. Legacy paragraphs retain old behavior.
- Fake online MP3 exercises decoding; fake offline WAV exercises direct PCM. No real provider is invoked.
- Synthetic mixed-layout fixtures export to WAV/MP3/M4A using installed FFmpeg within existing codec tolerance, including with normalization.
- Failure or cancellation preserves an existing final file, avoids stale audio inclusion, records the right job state and cleans incomplete output.
- Validation fails before synthesis/job side effects; used-role missing model errors are actionable.
- Audited legacy service/generation/export tests still pass; custom voice IDs, defaults and callback consumers work.

## Verification and completion

Add fake-provider structured service/generation tests and synthetic-media integration tests. Use deterministic non-speech fixtures to verify durations and final silence, not listening. Test cancellation at each relevant stage and modified metadata hashes. Do not run live TTS, model integrations, benchmarks or exhaustive voice tests. Record M14 evidence and any absent FFmpeg prerequisite; missing required media checks cannot be called a pass.

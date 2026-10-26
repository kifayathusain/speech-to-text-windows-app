# M12 — JSON document contract and validation

Initial status: NOT_STARTED. Dependency: current architecture and shared rules reviewed. Scope: document layer only; do not implement generation or redesign the GUI yet.

## Objective

Parse, validate and serialize the sample's structured conversation without losing role identity, direction notes, text, timing or extension data.

## Implementation tasks

1. Introduce typed document, speaker, segment, speech-setting and diagnostic models, preferably in `ttsapp/conversation_document.py`. Keep these independent of Tkinter and inference libraries.
2. Provide file and in-memory parsing entry points with identical semantic validation. Read UTF-8/BOM, enforce file size before loading and enforce equivalent byte/count/depth limits for in-memory input. Guard excessive nesting before passing data into recursive conversion; avoid a naive brace count that misreads strings.
3. Reject duplicate object keys at every depth, malformed JSON, unsupported schema versions, non-object roots, empty/wrong-type arrays, missing required fields, duplicate IDs, bad references, wrong types and non-finite numbers. Validate optional fields only when present; absence is different from null or a wrong type.
4. Follow shared limits and defaults. Omitted direction is empty; omitted pause is zero; omitted speed remains unset. Reject whitespace-only role labels/text and IDs with surrounding whitespace. Preserve original dialogue rather than silently normalizing the saved source.
5. Return errors with semantic paths and stable diagnostic codes. Syntax errors also include line and column. Aggregate independent semantic errors up to a documented bound of 100, then report additional errors were omitted. Never include private source text in default logs.
6. Preserve unknown root/speaker/segment/nested extension fields and issue warnings. Keep immutable core state or defensive copies so worker snapshots cannot be mutated through retained input dictionaries.
7. Add a serializer and atomic Save As helper that preserve known and unknown fields and all segment ordering. New documents may write `schema_version: 1`. Saving a document must not perform synthesis or implicitly write to its imported path.
8. Publish `docs/tts-input.schema.json` and a concise format guide. Keep `docs/tts-sample.json` unchanged as the compatibility fixture. Add a small separate example covering optional defaults and speed.
9. Define active-document identity separately from revision/content hash. A new import has a fresh identity unless explicitly reloading the same active source; edits advance revision without changing identity. M15 will connect this to UI state; M16 persists project identity.

## Expected files

New document module, schema/format guide, example and `tests/test_conversation_document.py`; adjust existing modules only for a small shared adapter if needed. No runtime schema-validation dependency is required. Existing text parser behavior remains untouched.

## Required acceptance

- Unmodified sample parses into three speakers and 26 ordered segments; explicit pause sum is 84, including a final 30.
- Duplicate role labels with distinct IDs are legal; duplicate IDs are rejected.
- Missing and explicit zero pauses resolve correctly; fractional values round-trip without silent truncation.
- Version/type/reference/limit errors are actionable, including bool-as-number and `schema_version: true`.
- Unknown fields round-trip; known invalid fields cannot hide as extensions.
- BOM, Unicode, embedded colons, newlines and direction notes survive source round-trip.
- The depth check handles braces/quotes inside text and rejects excessive nesting cleanly.
- Parse/serialize uses no network, model files or provider initialization.
- Atomic save failure preserves the previous destination and cleans temporary data.

## Verification and completion

Add focused parser/serializer/error tests including size/depth/count boundaries and source-copy isolation. Run audited existing parser regressions and changed-file Ruff. Record exact evidence under M12. The document layer may return warnings for unused speakers; provider-specific mapping validity belongs to M13. Do not claim GUI import acceptance in this milestone.

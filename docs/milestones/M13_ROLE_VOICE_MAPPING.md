# M13 — Role-to-voice mapping and effective settings

Initial status: NOT_STARTED. Dependency: M12 DONE. Read shared rules before editing.

## Objective

Resolve every declared role to a deterministic, editable provider voice and resolve effective generation settings without relying on widget positions or loading voice models.

## Implementation tasks

1. Introduce pure mapping/state helpers, preferably `ttsapp/speaker_mapping.py`. Model speaker ID, role, provider, selected stable voice ID, assignment origin, readiness hint and warnings independently of Tk variables.
2. Implement the shared precedence rules and deterministic fallback algorithm. Validate candidate imported/preset defaults using metadata; invalid hints produce warnings and fall through. Invalid explicit current/project assignments remain visible unresolved errors instead of being silently replaced.
3. Retain state under active document ID + speaker ID + provider ID. Same-document reload reconciles retained IDs; new-document imports start fresh unless an explicitly loaded matching project supplies assignments. Removing then creating a different role must not inherit stale state.
4. Preserve voice selections across provider switches and filtering. Filtering changes available suggestions, not selection identity. Resolve Piper using full catalog voice IDs, keeping model IDs and numeric speakers separate from application roles.
5. Populate all declared roles, including unused ones. Check generation readiness only for used roles. An absent local model gets a labeled catalog default, never an automatic download. Do not claim file presence proves integrity.
6. Support custom nonempty Edge IDs as today. When the two configured Edge defaults serve three roles, reuse deterministically and emit shared-voice diagnostics identifying affected roles.
7. Resolve speed as segment > role > job > provider default; retain the source of each effective override. Validate 0.5–2.0 and declared provider support. Do not turn an untouched disabled Edge speed widget into an explicit speed request.
8. Produce resolved segments with source identity/index, selected voice, dialogue, effective speed, pause and direction-status metadata, ready for M14. Keep source notes out of spoken text.
9. Distinguish informational note-only directions, partially supported requirements and unsupported explicit settings. Do not interpret prose into guessed speed, pitch or emotion.
10. Provide preflight data: role/used-role count, segments, word count with documented counting convention, exact silence total, errors and warnings. Do not present a calculated speech duration as measured output.
11. Provide reset-role/default and reset-unmapped helpers that cannot overwrite unrelated manual assignments. Persistent preferences are passed in as data here; M16 implements storage.

## Expected files

Mapping/resolution helpers, small additive desktop-option/shared representation changes and focused tests. Reuse provider metadata and existing model status APIs; do not expand Edge capabilities or rewrite provider/session code.

## Required acceptance

- All sample roles receive populated defaults. A repeated Edge voice is warned about, not represented as distinct.
- Given the same inputs, catalog order and preferences, resolution is repeatable.
- Row/segment reordering, insertion/deletion, search and provider switching preserve the right manual choices.
- New documents with identical role names do not inherit another document's edits.
- Same-document retained IDs reconcile safely; source identity and revision are not conflated.
- Missing/corrupt model readiness is actionable; metadata resolution neither downloads nor infers.
- Imported invalid hints fall through visibly; invalid explicit edits block used-role generation.
- All speed precedence combinations propagate correctly; explicit Edge speed fails before synthesis.
- Direction notes are preserved and limitations are honest; only dialogue is synthesis content.
- Unknown provider defaults can remain preserved extensions/hints without selecting an unsupported provider.

## Verification and completion

Use fake catalogs/status sources and parameterized pure-function tests for precedence, ties, shared voices, model hints and identity transitions. Run audited existing desktop-options/catalog regressions. Record M13 evidence and the interface M14 will consume. Do not redesign the GUI yet.

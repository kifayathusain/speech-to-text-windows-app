# Structured conversation JSON (version 1)

M12 supplies a document API in `ttsapp.conversation_document`. Desktop import,
voice mapping, generation and JSON CLI integration belong to M13–M16. Existing
`Speaker: text` input is unchanged. See the [sample](tts-sample.json),
[optional-field example](tts-input-example.json) and
[JSON Schema](tts-input.schema.json).

The root object requires nonempty `speakers` and `segments` arrays. Omitted
`schema_version` means integer 1. Each speaker requires a unique, case-sensitive
`id` and nonblank `role`. Duplicate display roles are allowed. Each segment
requires a declared `speaker` ID and nonblank `text`. IDs must already be trimmed;
references are never rewritten. Original role labels, text, punctuation, colons,
newlines and Unicode remain intact.

Speakers and segments accept optional string `voice_direction` notes (default
empty) and `speech` objects with optional numeric `speed` (default unset).
Speakers also accept `voice_defaults`, an object mapping trimmed provider IDs to
trimmed voice IDs. M12 validates their shape without resolving providers or
checking models. Directions are preserved notes; they do not control synthesis.
Later effective speed precedence is segment > role > job > provider default.
Explicit Edge speed is unsupported and must be rejected by later generation
validation. Importing this example does not synthesize anything.

Segments accept `pause_after_seconds`, default zero, including fractional values
and the final segment's pause. M14 will render these as PCM silence; M12 only
preserves and validates them. Existing five-second sentence/paragraph settings
are separate and unchanged.

Limits are centralized in the document module:

| Limit | Value |
| --- | --- |
| Input | 10 MiB UTF-8, including BOM/whitespace in serialized input |
| Speakers / segments | 1–1,000 / 1–10,000 |
| Explicit after-pause | 0–600 seconds |
| Total explicit silence | At most 86,400 seconds |
| Explicit speed | 0.5–2.0 |
| Container depth | 64, counting the root object as 1 |
| Diagnostics | First 100 errors, then one `diagnostics_omitted` sentinel; warnings independently bounded the same way |

Booleans, numeric strings, null and non-finite numbers are invalid for numeric
fields. Optional fields are validated when present; null never means omitted.
Unknown fields at any supported object level are retained and warned about;
nested extension payloads remain intact and must also contain valid finite JSON.
Duplicate keys at every depth are errors, including escaped spellings of the
same key. JSON Schema documents structural constraints; the Python validator
also enforces references, unique IDs, duplicate keys, cumulative silence,
finite numbers, byte size and depth. JSON Schema treats `1.0` as an integer;
the runtime deliberately requires the schema version to be a Python/JSON integer
token and rejects `1.0` as well as `true`.

## Python API

```python
from pathlib import Path
from ttsapp.conversation_document import load_document, save_document_as

document = load_document(Path("docs/tts-sample.json"))
edited_source = document.to_dict()
edited_source["segments"][0]["text"] = "Updated dialogue"
edited = document.with_data(edited_source)
save_document_as(edited, Path("conversation-copy.json"))
```

`parse_document_text(str_or_bytes)` accepts UTF-8 with an optional BOM.
`parse_document_data(tree)` accepts only JSON-compatible Python dict/list trees;
its equivalent byte limit uses compact unescaped UTF-8 JSON. Both apply the same
semantic validator as `load_document`. Depth is checked iteratively before
recursive decoding/encoding, respecting quoted braces and escaped quotes.
`DocumentValidationError.diagnostics` contains stable codes, semantic paths and
messages. Syntax errors additionally include line and column. No default logs
or exception messages dump dialogue text. `DocumentIOError` reports file errors.

Parsed core records are frozen and voice defaults are read-only. `to_dict`
returns an isolated copy including extension payloads. `serialize_document`
returns the validated source JSON without a BOM, preserving source values,
field absence and formatting. Python-tree input uses compact unescaped JSON.
Retaining the source also prevents number reformatting from expanding a valid
document beyond the byte limit when it is saved. Saving uses
a temporary file beside the explicit destination, flush/fsync and atomic replace,
with temporary-file cleanup on failure. The destination parent must exist.
Importing never implicitly writes to its source. These synchronous document
operations do not have a cancellation contract or initialize providers/models.

Every new import receives a fresh `document_id`, initially revision 0. Content
hashes use sorted-key compact UTF-8 JSON and exclude active identity/revision.
`document.with_data(tree)` validates an edit, retains identity and advances the
revision; invalid edits leave the old snapshot intact. Explicit
`load_document(path, reload_of=active)` (or either parse function's `reload_of`)
retains active identity and advances revision. Only pass `reload_of` when the
caller intentionally reloads the same active source; M15 will manage that UI
decision, and M16 will persist project identity.

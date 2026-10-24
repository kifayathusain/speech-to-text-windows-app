# Python Coding Standards

This document is the authoritative source for project coding conventions.
[`../AGENTS.md`](../AGENTS.md) is the mandatory entry point for every Codex
session. These standards apply to all new and modified code in every milestone:
Edge TTS, Piper, Kokoro, model management, text processing, preview, audio
exports, performance, and Windows packaging.

Apply them incrementally. Preserve working features and unrelated uncommitted
changes; do not rewrite or bulk-format the codebase to adopt this policy.

## 1. Core Principles

All source code must prioritize:

1. Readability
2. Maintainability
3. Simplicity
4. Correctness
5. Testability
6. Performance where justified

**Human readability is more important than reducing the number of lines of code.**

Do not write compressed code simply to make implementations shorter.

Follow PEP 8, PEP 257, and modern Python conventions.

## 2. Naming Conventions

Use descriptive names.

- Classes: `PascalCase`
- Functions: `snake_case`
- Variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_snake_case`

Avoid single-letter variable names except for conventional, obvious local use.

Bad:

```python
def p(t, v):
    return v.s(t)
```

Good:

```python
def synthesize_speech(
    text: str,
    voice: VoiceConfiguration,
) -> AudioResult:
    return voice.provider.synthesize(text)
```

## 3. Avoid Compressed Statements

Do not combine independent statements on the same line.

Bad:

```python
if not text: return None
```

Good:

```python
if not text:
    return None
```

Bad:

```python
a = load(); b = process(a); save(b)
```

Good:

```python
source_audio = load_audio()
processed_audio = process_audio(source_audio)
save_audio(processed_audio)
```

## 4. Prefer Readable Control Flow

Avoid deeply nested conditional expressions.

Bad:

```python
voice = a if x else b if y else c
```

Good:

```python
if prefer_british_voice:
    voice = british_voice
elif prefer_american_voice:
    voice = american_voice
else:
    voice = default_voice
```

Use early returns when they simplify code.

Do not replace clear conditional logic with clever expressions.

## 5. Functions and Methods

Functions should perform one logical responsibility.

Guidelines:

- Prefer small, focused functions.
- Aim for approximately 10–40 lines where practical.
- Do not enforce arbitrary length limits.
- Extract reusable logic when it improves clarity.
- Avoid excessive parameters.
- Avoid hidden side effects.
- Keep business rules separate from I/O.

Do not split a clear function into numerous trivial wrappers solely to reduce line counts.

## 6. Classes

Follow the Single Responsibility Principle.

A class should have one clear purpose.

Examples:

- `KokoroTTSProvider`: Kokoro voice synthesis
- `PiperTTSProvider`: Piper voice synthesis
- `ModelManager`: Local model lifecycle
- `AudioExporter`: Final audio export
- `TextChunker`: Text segmentation

Avoid god classes that manage UI, inference, downloads, and exports together.

Avoid speculative abstractions and unnecessary inheritance.

## 7. Type Hints

Use type hints for public functions, methods, and important internal interfaces.

Example:

```python
from pathlib import Path


def export_audio(
    source_file: Path,
    output_file: Path,
    bitrate: str = "192k",
) -> Path:
    ...
```

Prefer explicit return types.

Use dataclasses or typed models for structured data where appropriate.

Avoid untyped dictionaries when a stable data structure would be clearer.

## 8. Error Handling

Handle failures explicitly.

Bad:

```python
try:
    generate()
except:
    pass
```

Good:

```python
try:
    generate_audio()
except ModelNotInstalledError as error:
    logger.error(
        "Required voice model is unavailable: %s",
        error,
    )
    raise
```

Requirements:

- Catch specific exceptions.
- Do not silently ignore failures.
- Do not expose internal stack traces directly in the UI.
- Preserve exception causes when helpful.
- Use domain-specific exceptions for expected application errors.
- Clean up temporary resources reliably.

## 9. Logging

Use the standard Python `logging` module or the repository's existing logging abstraction.

Do not use `print()` for application diagnostics.

Use appropriate levels:

- DEBUG: Technical diagnostics
- INFO: Normal operations
- WARNING: Recoverable problems
- ERROR: Failed operations
- CRITICAL: Application-level failure

Never log private input text, credentials, or sensitive configuration values by default.

## 10. Comments and Docstrings

Comments should explain why a decision exists, not repeat obvious code.

Bad:

```python
# Increment counter
counter += 1
```

Good:

```python
# Preserve the original chunk order so audio can be
# reconstructed after an interrupted generation.
completed_chunks.sort(key=lambda chunk: chunk.index)
```

Write docstrings for public modules, classes, and functions where helpful.

Use a consistent docstring style.

Avoid excessive comments that merely narrate code.

## 11. Formatting

Use:

- Four-space indentation
- Consistent imports
- Blank lines between logical sections
- Trailing commas for multiline collections and calls where appropriate
- Ruff formatting
- Maximum preferred line length of 88 characters

Prefer multiline formatting when it improves readability.

Example:

```python
generation_request = SpeechGenerationRequest(
    text=input_text,
    voice_id=selected_voice.identifier,
    provider_id=selected_provider.identifier,
    speaking_rate=speaking_rate,
    output_format=output_format,
)
```

Do not manually compress multiline expressions to save vertical space.

## 12. TTS Provider Standards

Each TTS provider must:

- Implement the common provider interface.
- Keep provider-specific code isolated.
- Declare supported capabilities.
- Validate configuration.
- Provide actionable errors.
- Clean up temporary resources.
- Support cancellation where feasible.
- Avoid direct dependencies on UI widgets.

Do not duplicate common audio export logic across providers.

## 13. Desktop UI Standards

- Keep business logic outside event handlers.
- Never block the UI thread with inference or FFmpeg work.
- Use thread-safe progress reporting.
- Avoid direct cross-thread UI modifications.
- Keep UI methods focused.
- Centralize state transitions where practical.

## 14. Resource Management

- Prefer context managers.
- Close files properly.
- Terminate subprocesses safely.
- Release audio buffers.
- Avoid retaining unused models in memory.
- Handle cancellation consistently.
- Remove temporary files on failure.

## 15. Dependency Management

- Use dependencies only when justified.
- Pin or constrain dependencies appropriately.
- Document why major dependencies are needed.
- Prefer maintained packages.
- Keep GPU dependencies optional or excluded.
- Review security and license implications.

## 16. Testing Standards

Use pytest unless the repository already has a justified alternative.

Tests must:

- Have descriptive names.
- Test observable behavior.
- Cover success and failure paths.
- Avoid brittle internal implementation assumptions.
- Use temporary directories for filesystem tests.
- Mock external network calls in unit tests.
- Keep real model inference tests identifiable.
- Verify cleanup and cancellation behavior.

## 17. Code Review Checklist

Before completing a change:

- [ ] Code follows PEP 8.
- [ ] Variable and method names are meaningful.
- [ ] No unnecessary one-line compressed logic exists.
- [ ] Functions have focused responsibilities.
- [ ] Errors are handled properly.
- [ ] Type hints are appropriate.
- [ ] No unnecessary abstractions were introduced.
- [ ] Existing features remain functional.
- [ ] Tests pass.
- [ ] Relevant documentation is updated.

## 18. Agent-Specific Requirements

Codex must not optimize for fewer lines of code.

Avoid:

- Excessively condensed comprehensions
- Nested ternary expressions
- Multiple statements separated by semicolons
- Cryptic variable names
- Dense one-line lambdas
- Unnecessary dynamic programming techniques
- Large monolithic functions
- Clever metaprogramming without a clear requirement
- Premature optimization

Prefer explicit, conventional Python that another developer can understand without additional explanation.

These standards are mandatory for all new and modified application code.

## 19. Existing Architecture and Compatibility

The existing CLI entry points (`main.py`, `gen_audio.py`) and Tkinter desktop
entry point (`app.py`, `ttsapp/gui.py`) delegate generation to
`ttsapp/service.py`. Parsing lives in `ttsapp/parser.py`, Edge synthesis in
`ttsapp/tts_engine.py`, and FFmpeg operations in `ttsapp/audio_combiner.py`.
Shared defaults live in `ttsapp/config.py`.

Preserve those boundaries and the existing Edge TTS/FFmpeg workflow. Introduce
provider changes incrementally in their assigned milestone. Provider classes
now live under `ttsapp/providers`; model lifecycle, preview, and validated
exports have dedicated modules. See `docs/architecture/ARCHITECTURE.md` for
the current implementation. Keep model lifecycle, synthesis, preview orchestration,
audio exports, and UI responsibilities separate without imposing a new
framework or moving modules merely to match a suggested directory structure.

Python 3.10+ remains the documented compatibility floor. Ruff targets Python
3.10 so automatic modernization does not introduce syntax requiring a newer
interpreter. Verify dependency compatibility when adding a provider or runtime.

## 20. Tooling and Milestone Completion Gate

Ruff and pytest configuration lives in the repository-root `pyproject.toml`.
Install development tools alongside application dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
```

Run the project checks from the repository root:

```powershell
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q
```

Ruff checks imports, Python errors, common bug patterns, modernization, and
simplification, including E701/E702 rules against compressed statements.
Readability, type-hint quality, responsibility boundaries, and error handling
also require manual review; passing tools alone is insufficient. Do not apply
a simplification suggestion if it obscures explicit control flow; revise the
surrounding design while preserving readability. Do not disable rules merely
to obtain a passing result.

Use `ruff format <changed Python paths>` only within the intended change scope.
Never run a repository-wide formatter or automatic lint fix as an unrelated
cleanup. Run relevant tests after each behavior change and the existing suite
before completion. New or changed behavior requires automated tests covering
applicable failures, cancellation, and resource cleanup.

Unit tests must run without network access or real inference. Mark tests that
need external executables/services with `integration`, and actual model
inference tests with `real_model`. Markers describe requirements; they do not
skip tests automatically. Record the environment, command, and reason for any
test that cannot run. Relevant real-model and Windows acceptance checks remain
required before their milestone can be DONE.

Before changing any milestone to DONE, record this gate in
[`milestones/MILESTONE_TRACKER.md`](milestones/MILESTONE_TRACKER.md):

- [ ] Acceptance criteria pass, including applicable real-model/Windows checks.
- [ ] Ruff formatting and lint checks pass for the milestone's changed Python
      files, with exact commands and results recorded.
- [ ] Repository-wide Ruff checks and the existing automated suite were run;
      pre-existing violations are reported separately by file and rule.
- [ ] Tests for changed behavior, failures, cancellation, and cleanup pass.
- [ ] Manual review confirms descriptive names, focused responsibilities,
      appropriate type hints/docstrings, explicit errors and control flow, and
      no compressed statements or unnecessary abstractions.
- [ ] Architecture boundaries, existing features, and unrelated work are preserved.
- [ ] Documentation and validation evidence are current, with limitations listed.

Pre-existing violations outside the milestone scope may remain documented;
they must not hide introduced regressions. New or modified code must pass its
relevant checks. Unmet acceptance criteria, introduced failures, or unavailable
required validation block DONE; record a reproducible reason rather than
claiming completion. Preserve historical statuses when adding this gate and
record a separate compliance review instead of retroactively asserting a pass.

# AGENTS.md — Codex Project Instructions

## Purpose

This repository contains a Windows Text-to-Speech desktop application using Python, Microsoft Edge TTS, FFmpeg, and local AI voice models.

All AI coding agents, including Codex, must follow the repository's development standards.

This file is the mandatory entry point for every Codex session.
[`docs/CODING_STANDARDS.md`](docs/CODING_STANDARDS.md) is the authoritative
source for project coding conventions; the rules below summarize that policy.

## Mandatory Instructions

Before implementing any change:

1. Read `docs/CODING_STANDARDS.md`.
2. Review the current application architecture.
3. Read `docs/milestones/MASTER_PLAN.md`, the milestone tracker, and the relevant
   milestone documents.
4. Understand the existing implementation before editing.
5. Identify the smallest maintainable change needed.

## Code Quality Rules

- Write clean, readable, human-maintainable code.
- Follow PEP 8 and relevant Python best practices.
- Prioritize clarity over code brevity.
- Do not compress multiple statements into one line.
- Avoid overly clever, cryptic, or unnecessarily abstract implementations.
- Use meaningful and descriptive names.
- Keep functions focused on one responsibility.
- Use explicit control flow.
- Write appropriate type hints.
- Add useful docstrings for public classes and functions.
- Avoid unnecessary duplication.
- Separate business logic from UI code.
- Handle errors explicitly.
- Preserve existing working functionality.
- Add automated tests for changed behavior.

## Formatting

- Prefer a maximum line length of 88 characters.
- Use four spaces for Python indentation.
- Use Ruff for formatting and linting.
- Never disable linting rules merely to avoid fixing code quality issues.
- Never use minified or compressed Python code.

## Architecture

- Maintain clear module boundaries.
- Use the existing architecture unless a change is justified.
- Keep TTS providers behind a common interface.
- Keep FFmpeg operations separate from synthesis logic.
- Keep model management separate from the UI.
- Use dependency injection where it genuinely improves testability.
- Avoid overengineering or unnecessary frameworks.

## Testing

- Run relevant tests after each change.
- Add tests for new functionality.
- Test error paths, cancellation, and resource cleanup.
- Do not mark a milestone complete if acceptance criteria are unmet.
- Document any tests that cannot be executed.

## Milestone Execution

Follow `docs/milestones/MILESTONE_TRACKER.md`.

- Implement milestones sequentially.
- Keep each milestone scoped.
- Update documentation after meaningful architectural changes.
- Verify acceptance criteria before marking DONE.
- Do not introduce unrelated refactoring.
- Apply the coding standards to every milestone, including Edge TTS, Piper,
  Kokoro, model management, text processing, preview, and audio exports.
- Before marking any milestone DONE, pass the coding standards completion gate
  in `docs/CODING_STANDARDS.md` and record the evidence in the tracker.
- Preserve existing milestone statuses and completed work. Never infer DONE
  from the presence of files or existing features.

## Git Safety

- Preserve existing uncommitted changes.
- Do not automatically commit or push.
- Never automatically commit to `main`.
- Do not use destructive Git commands without explicit authorization.

## Final Review

Before reporting completion, verify:

- Code is readable and consistently formatted.
- Functions and classes have clear responsibilities.
- No unnecessary one-line or compressed expressions were introduced.
- Type hints and error handling are appropriate.
- Tests pass.
- Documentation reflects the implementation.
- Relevant Ruff formatting and lint checks pass, and existing violations are
  reported separately without unrelated bulk formatting or suppressed rules.

These rules apply to every Codex session and every milestone.

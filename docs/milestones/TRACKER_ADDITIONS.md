# Documentation setup and tracker additions

These are instructions for the implementation session. This packet has not changed repository records or started a milestone.

## Register the follow-up

1. Check the actual current tracker before editing. If an M12-or-later ID is already occupied, do not overwrite its scope or history; report the conflict and reconcile numbering explicitly.
2. Add the packet's execution rules and milestone files under `docs/milestones/` without replacing existing files. `START_HERE.md` may be named `M12_M17_START_HERE.md` there to avoid a generic filename collision.
3. Add a clearly labeled M12–M17 follow-up section to `MASTER_PLAN.md` and link to these files. Preserve historical scope and status records.
4. Add the rows below to `MILESTONE_TRACKER.md`, initially NOT_STARTED. Mark only the requested milestone IN_PROGRESS when actual implementation begins.
5. Record the authorization: the user approved the JSON/multi-speaker plan and requested implementation instructions starting at M12. Actual implementation starts only when the subsequent session requests it; document-only setup does not imply implementation or acceptance.
6. Record that M12–M17 may proceed independently of M10's clean-machine blocker, without waiving or changing that blocker. The shared safe-verification boundary applies to the new follow-up only.

## Rows to add

| ID | Scope | Recorded status | Coding standards compliance |
| --- | --- | --- | --- |
| M12 | JSON Document Contract and Validation | NOT_STARTED | Pending; M12_JSON_DOCUMENT_CONTRACT.md |
| M13 | Role-to-Voice Mapping and Effective Settings | NOT_STARTED | Pending; M13_ROLE_VOICE_MAPPING.md |
| M14 | Structured Generation and Exact Segment Pauses | NOT_STARTED | Pending; M14_STRUCTURED_GENERATION.md |
| M15 | Responsive Multi-Speaker Windows GUI | NOT_STARTED | Pending; M15_RESPONSIVE_GUI.md |
| M16 | Saved Projects, Presets and JSON CLI | NOT_STARTED | Pending; M16_PROJECTS_PRESETS_CLI.md |
| M17 | Integrated Acceptance and Documentation | NOT_STARTED | Pending; M17_INTEGRATED_ACCEPTANCE.md |

Convert filenames to local Markdown links when installing the rows.

## Evidence template for each milestone

```markdown
### Mxx — [scope] — [actual date]

Status: [IN_PROGRESS / DONE / BLOCKED]
Dependency evidence: [prior milestone and reference]
Implemented behavior and changed files: [...]

Environment:
- Interpreter and tool versions: [...]
- Windows/scaling/media-tool availability where applicable: [...]

Acceptance:
- [criterion]: [test or manual evidence and result]
- [criterion]: [...]

Verification commands and results:
- [exact safe command]: [counts/outcome]
- Changed-file Ruff format/lint: [...]
- Repository-wide Ruff: [results; separate existing file/rule findings]
- Audited regression allowlist: [exact files/node IDs or committed manifest]
- Excluded checks: [IDs/files and no-download/no-live-voice reason]

Failure/cancellation/cleanup evidence: [...]
Manual readability/architecture review: [...]
Documentation updates: [...]
Unmet required checks and limitations: [...]
Next dependency: [...]

No models downloaded, live voice synthesis, voice-quality/comparison tests,
provider benchmarks or exhaustive voice checks were performed for this milestone.
[Include the previous sentence only if true; report any breach candidly.]
Historical statuses including M10's clean-machine blocker remain unchanged.
```

Use real execution dates and measured results. Do not copy old test totals as new evidence, infer DONE from file presence, or reinterpret excluded quality checks as feature failures. Missing new required checks still prevent the corresponding feature milestone from reaching DONE.

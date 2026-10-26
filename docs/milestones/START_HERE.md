# Codex implementation instructions: M12–M17

Prepared 26 October 2026 for `D:\Projects\speech-to-text-windows-app`.

This packet translates the approved JSON/multi-speaker plan into six sequential implementation milestones. Preparation of this packet does not authorize starting implementation in the current chat. Application code and repository milestone records have not been changed.

## How to use

Open the repository in a Codex chat. Attach this packet or copy its Markdown files into `docs/milestones/` as a documentation-only setup step. Preserve existing documents. Read `M12_M17_EXECUTION_RULES.md` and the target milestone together; neither replaces `AGENTS.md` or the coding standards.

For a bounded first implementation session, use this prompt:

```text
Implement M12 in speech-to-text-windows-app using the attached M12–M17 packet.
First read AGENTS.md, docs/CODING_STANDARDS.md, the existing architecture,
MASTER_PLAN.md, MILESTONE_TRACKER.md, M12_M17_EXECUTION_RULES.md, and
M12_JSON_DOCUMENT_CONTRACT.md. Inspect current code before editing.

Register the follow-up roadmap without altering historical milestone statuses.
Implement and verify M12 only. Preserve Edge TTS, FFmpeg, Piper, Kokoro,
legacy workflows and unrelated work. Do not download voice models or run
live synthesis, quality/comparison tests, benchmarks or exhaustive voice checks.
Use reviewed offline tests and fake providers. Record evidence and exclusions.
Do not commit or push. Stop after M12 and report results and any unmet gate.
```

For each later session, replace both M12 references and the target filename with the next milestone. Explicitly request several milestones if you want Codex to continue across those boundaries; a single-milestone prompt is intentionally bounded.

## Roadmap

| ID | Scope | Depends on | Main result |
| --- | --- | --- | --- |
| M12 | JSON document contract and validation | Existing architecture | Typed parser/serializer and unchanged sample support |
| M13 | Role-to-voice mapping and effective settings | M12 | Deterministic editable defaults independent of row positions |
| M14 | Structured generation and exact pauses | M13 | Ordered speech/silence, final pause and compatibility |
| M15 | Responsive multi-speaker GUI | M14 | Import, editing, role controls, safe preview and adaptive layout |
| M16 | Saved projects, presets and CLI | M15 | Reopenable work, reusable assignments and JSON CLI input |
| M17 | Integrated acceptance and documentation | M16 | Verified feature, recorded evidence and accurate user guidance |

All six start as NOT_STARTED when registered. M01–M09 and M11 retain their recorded DONE statuses; M10 retains BLOCKED on clean Windows 11 evidence. M12–M17 are an independently authorized follow-up and do not require changing M10's status.

## Files in this packet

- `M12_M17_EXECUTION_RULES.md`: shared architecture, compatibility, validation and testing rules.
- `M12_JSON_DOCUMENT_CONTRACT.md`
- `M13_ROLE_VOICE_MAPPING.md`
- `M14_STRUCTURED_GENERATION.md`
- `M15_RESPONSIVE_GUI.md`
- `M16_PROJECTS_PRESETS_CLI.md`
- `M17_INTEGRATED_ACCEPTANCE.md`
- `TRACKER_ADDITIONS.md`: append-only roadmap/status/evidence instructions.

Deferred scope remains deferred: mixed providers within a job, automatic natural-language direction interpretation, new emotion/pitch/SSML support, waveform editing, incremental regeneration/resume, extra voice validation and framework migration.

# Text Processing and Tracked Generation

Original Edge CLI/UI calls retain their prior default segmentation and output
behavior. Offline providers automatically use the processed pipeline. Edge can
opt in with `text_settings=TextProcessingSettings(...)` in the service API.

Normalization applies Unicode NFC and collapses synthesis whitespace, retaining
punctuation, language, dates, numbers, and abbreviations. Original parsed input
remains separate in memory. No abbreviation/number expansion guesses meaning.
Blank script lines mark a paragraph break before the next dialogue entry; they
do not create empty speech or change speaker ordering.

Chunks partition every normalized source character in order. Complete paragraphs
are kept when within limits, then boundaries prefer complete sentences, then
whitespace, then an unavoidable long-word split. Common abbreviations/initials,
decimals, closing quotes, CJK punctuation, and combining/joined characters have
explicit handling. The configured maximum is capped by the selected provider's
limit. A Unicode cluster that cannot fit is rejected rather than silently lost.

`TextProcessingSettings` defaults: maximum 1,000 characters, zero extra sentence
pause (engine prosody), and 0.35 seconds between paragraphs. An explicit nonzero
sentence pause separates sentences and adds exact PCM silence. Pauses must be
finite and between zero and five seconds. MP3/WAV final output is supported.
No leading or trailing artificial silence is added. Mixed-rate voice segments
remain explicitly rejected pending M08 normalization.

Processed jobs use isolated `output_dir/job-<id>` directories, protecting their
chunks from concurrent/repeated job overwrites. Local synthesis writes lossless
WAV; opted-in Edge MP3 is decoded once to PCM before pause insertion/combination.
Only final MP3 export is lossy. Original default Edge stream copy is preserved.

Each job atomically maintains `generation.json`: provider, request fingerprint,
settings, normalized source spans, text hashes, output file hashes, and chunk/job
states. Private input text is not written into this metadata or diagnostic logs.
Completed chunks remain available after failure/cancellation. These identities
support future safe resumption; automatic resume/reuse is not yet exposed, and
unknown files are never implicitly trusted as completed synthesis.

The existing line-progress callback fires once per completed dialogue entry.
`on_chunk_progress(index, total, chunk)` supplies finer progress for processed
jobs. Cancellation checks run between chunks, while local/Edge providers clean
incomplete files, before pauses, and before final output publication. Blocking
FFmpeg work still finishes its current process before cancellation returns;
process interruption is later export scope. Existing final output survives
controlled synthesis, conversion, or export cancellation/failure.

A metadata write failure before export stops the job. If only the final metadata
update fails after valid media was committed, a warning is logged and successful
media remains the result; the last valid job record remains available. This
avoids reporting successful audio as a failed/rolled-back export.

M06 real-model, long-text, PCM-duration, and human listening evidence is recorded
in [the milestone](../milestones/M06_TEXT_PROCESSING.md).

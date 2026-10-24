# M04 Real Kokoro CPU Measurements

Measured 2026-10-24 on Windows 11 build 26300 with signed official Python
3.13.17, kokoro-onnx 0.6.1, ONNX Runtime 1.31.0 CPU, NumPy 2.5.4, and FFmpeg 7.1.
The unquantized 82M-parameter v1.0 ONNX export and voices were verified against
upstream release SHA-256. Two intra-op CPU threads were configured; no GPU.
Processor model could not be read because the sandbox denied CIM access, so do
not use these observations as a cross-machine performance guarantee.

Command:

```powershell
python -m scripts.benchmark_kokoro --model-dir .venv/validation-models/kokoro --output-dir .venv/benchmarks/kokoro-m04 --cpu-threads 2
```

Model verification/load: **3.31 seconds**. First completed audio: **9.00 seconds**.
First completed audio includes loading and the first bounded segment; it is not
a streaming first-sample measurement. Synthesis includes integrity checks and
PCM writing, but excludes model initialization and final export. Real-time
factor is synthesis processing seconds divided by generated audio seconds.

| Voice | Input | Synthesis s | Audio s | RTF | Export s |
| --- | --- | --- | --- | --- | --- |
| af_heart | short | 5.70 | 3.64 | 1.57 | 0.19 |
| af_heart | paragraph | 14.18 | 9.71 | 1.46 | 0.19 |
| bf_emma | short | 5.40 | 3.58 | 1.51 | 0.19 |
| bf_emma | paragraph | 11.82 | 9.16 | 1.29 | 0.31 |

These runs were slower than real time at two CPU threads. Process peak working
set reached approximately 635 MiB; process CPU ranged from 175% to 194%, meaning
roughly two busy logical cores. Working-set peaks are cumulative for the process.
Source outputs were mono 24 kHz PCM16. All four had nonzero RMS, valid sample
ranges, and zero measured clipped samples. These checks do not measure semantic
speech accuracy or human-perceived naturalness. Human listening is pending; no
naturalness claim is made. No performance tuning milestone is complete yet.

[Raw measurements](M04_KOKORO.json) preserve the actual numbers. The generated
WAV/MP3 files remain in ignored `.venv/benchmarks/kokoro-m04` for listening;
model/audio binaries were not added to Git.

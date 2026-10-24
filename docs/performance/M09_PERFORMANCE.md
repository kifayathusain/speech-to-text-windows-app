# M09 CPU performance measurements

Measured on 2026-10-25, Windows 11 build 26300, Intel Core i5-1235U
(10 cores, 12 logical processors), signed Python 3.13.17, ONNX Runtime 1.31.0
CPU, FFmpeg/FFprobe 9.0.2. Models are the pinned catalog assets; Kokoro remains
the full unquantized 82M export. [Raw reports](M09_BENCHMARKS.json) contain CPU
time, process CPU percentage, native duration, PCM levels/clipping, and export
time per case. No mocked inference or timings are included.

## Observations

RTF is synthesis seconds divided by native audio seconds; lower is faster.
Initialization includes import, full integrity verification, and model loading.
First audio means a complete native file, not streaming time to first sound.
Peak memory is cumulative process working set, measured after each case.
The two input sizes are 51 and 164 characters; Kokoro and Edge use two voices,
Piper uses one. These small samples do not represent all long documents.

| Run | Successful cases | Load seconds | First audio seconds | Median RTF | Peak MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| after-kokoro-noarena | 4 | 3.79 | 9.25 | 1.487 | 591.6 |
| after-kokoro-t4 | 4 | 3.13 | 7.77 | 1.377 | 648.0 |
| after-piper-noarena | 4 | 4.75 | 5.17 | 0.126 | 204.3 |
| after-piper-t1 | 2 | 3.88 | 4.37 | 0.128 | 206.9 |
| after-piper-t2 | 2 | 4.99 | 5.31 | 0.101 | 207.1 |
| after-piper-t4 | 2 | 5.18 | 5.49 | 0.088 | 205.3 |
| before-piper | 2 | 2.99 | 3.54 | 0.163 | 208.6 |
| before-t1 | 4 | 2.07 | 12.30 | 2.799 | 634.6 |
| before-t2 | 4 | 1.78 | 6.48 | 2.317 | 634.9 |
| before-t4 | 4 | 3.74 | 9.73 | 1.340 | 635.3 |
| confirm-kokoro-noarena | 8 | 3.55 | 9.38 | 1.500 | 597.1 |
| edge | 4 | 0.00 | 3.34 | 0.484 | 49.4 |
| final-kokoro-noarena | 4 | 1.84 | 7.35 | 1.615 | 592.4 |

## Selected defaults and tradeoffs

- Four intra-operation threads, one sequential CPU session for both local
  providers. Constructors and the benchmark CLI allow other positive counts.
  Four threads performed best in this 1/2/4-thread sweep; other CPUs may differ.
- Kokoro disables the CPU memory arena. Peak working set fell from 635.3 MiB
  in the four-thread baseline to 591.6–597.1 MiB across arena-disabled runs.
  The final isolated run measured 592.4 MiB and RTF 1.615. This exchanges some
  throughput for lower memory: arena-enabled after-change RTF was 1.377.
  Full precision weights, voice styles, speed, phonemization and chunking remain
  unchanged. No faster-than-real-time Kokoro claim is made.
- Piper keeps its arena: disabling it saved only about 1 MiB and median RTF
  worsened from 0.088 to 0.126. Four threads improve warm throughput versus the
  original default session (0.163), while measured cold first completion rises
  from 3.54 to 5.49 seconds. This once-per-session startup cost is retained for
  repeated previews/long synthesis; explicit thread settings permit tuning.
- Warm requests reuse verified resident weights. Kokoro retains only the four
  catalog styles, closes the voice archive, and passes resident style arrays to
  the public runtime API. Every new runtime load re-verifies full asset hashes;
  explicit Model library Verify continues to scan actual files. Closing or
  switching sessions prevents reuse of old weights after library modification.
- ProviderManager reuses the selected provider without another full disk scan.
  The bounded preview cache remains voice/text/speed/asset-version specific.

The confirmation repeat briefly overlapped with GUI acceptance and is labeled
in raw data. The final run was isolated. Thermal state, background scheduling,
filesystem caching and Edge service/network conditions vary. Do not attribute
all timing differences to caching or extrapolate laptop results to every CPU.
The original Kokoro baseline used legacy export; newer benchmark reports use
validated export, so export timings are not a controlled before/after comparison.

All real benchmark cases succeeded. Matching Kokoro outputs retained identical
frame counts; PCM samples were not bit-identical across executions. Peak/RMS and
clipping checks establish valid output, not equal perceived naturalness. The M06
human acceptance of joins remains recorded separately; no new listening score
is inferred from these objective measurements.

## Reproduce

Install `requirements.txt`, `requirements-kokoro.txt`, `requirements-piper.txt`
and `requirements-benchmark.txt` in Python 3.10–3.13. Put FFmpeg and FFprobe on
PATH and obtain verified catalog assets through Model library. Use a different
empty output directory for every run; reports never overwrite earlier samples.

```powershell
python -m scripts.benchmark_providers --provider kokoro --model-dir C:/models/kokoro --output-dir C:/bench/kokoro --cpu-threads 4 --no-memory-arena
python -m scripts.benchmark_providers --provider piper --model-dir C:/models/piper --output-dir C:/bench/piper --cpu-threads 4
python -m scripts.benchmark_providers --provider edge --output-dir C:/bench/edge
```

Use `--repetitions 2` for repeated samples. Edge sends these fixed public sample
texts to its real online service and requires connectivity. Local providers do
not download assets while benchmarking. Session tuning follows the official
[ONNX thread guide](https://onnxruntime.ai/docs/performance/tune-performance/threading.html)
and [session API](https://onnxruntime.ai/docs/api/python/api_summary.html).

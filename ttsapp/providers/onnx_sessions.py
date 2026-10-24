"""Shared optional CPU runtime settings; importing metadata needs no ONNX runtime."""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from onnxruntime import InferenceSession


def create_cpu_session(
    model_path: Path, cpu_threads: int, memory_arena: bool
) -> "InferenceSession":
    """Create a bounded, explicitly CPU-only session without GPU fallback."""
    import onnxruntime

    onnxruntime.disable_telemetry_events()
    settings = onnxruntime.SessionOptions()
    settings.intra_op_num_threads = cpu_threads
    settings.inter_op_num_threads = 1
    settings.execution_mode = onnxruntime.ExecutionMode.ORT_SEQUENTIAL
    settings.enable_cpu_mem_arena = memory_arena
    return onnxruntime.InferenceSession(
        str(model_path), sess_options=settings, providers=["CPUExecutionProvider"]
    )

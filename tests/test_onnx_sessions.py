"""CPU settings are bounded explicitly without importing optional runtimes eagerly."""

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from ttsapp.providers.onnx_sessions import create_cpu_session


def test_cpu_session_options_are_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    settings = SimpleNamespace()
    runtime = ModuleType("onnxruntime")
    runtime.disable_telemetry_events = lambda: calls.append("telemetry disabled")
    runtime.SessionOptions = lambda: settings
    runtime.ExecutionMode = SimpleNamespace(ORT_SEQUENTIAL="sequential")

    def session(path: str, **kwargs: object) -> object:
        assert path == str(Path("model.onnx"))
        assert kwargs["providers"] == ["CPUExecutionProvider"]
        assert kwargs["sess_options"] is settings
        return object()

    runtime.InferenceSession = session
    monkeypatch.setitem(sys.modules, "onnxruntime", runtime)
    create_cpu_session(Path("model.onnx"), 4, False)
    assert calls == ["telemetry disabled"]
    assert settings.intra_op_num_threads == 4
    assert settings.inter_op_num_threads == 1
    assert settings.execution_mode == "sequential"
    assert settings.enable_cpu_mem_arena is False

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import numpy as np
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    importlib.import_module("pymc")
except ModuleNotFoundError:
    class _FakeModel:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    def _fake_normal(name, mu=0.0, sigma=1.0, observed=None, shape=None):
        if observed is not None:
            return np.asarray(observed, dtype=float)
        if isinstance(mu, np.ndarray):
            return mu.astype(float)
        return float(mu)

    def _fake_half_normal(name, sigma=1.0):
        return float(abs(sigma))

    def _fake_sample(draws=2000, **kwargs):
        size = max(int(draws), 5)
        return {
            "intercepto": np.linspace(110.0, 120.0, num=size),
            "pendiente": np.linspace(-2.5, -1.8, num=size),
            "sigma_ventas": np.linspace(3.0, 5.0, num=size),
            "beta_1": np.linspace(-0.4, -0.1, num=size),
            "beta_2": np.linspace(0.0, 0.05, num=size),
        }

    fake_pymc = types.ModuleType("pymc")
    setattr(fake_pymc, "Model", _FakeModel)
    setattr(fake_pymc, "Normal", _fake_normal)
    setattr(fake_pymc, "HalfNormal", _fake_half_normal)
    setattr(fake_pymc, "sample", _fake_sample)
    sys.modules["pymc"] = fake_pymc


@pytest.fixture
def sample_observations() -> list[dict[str, float]]:
    return [
        {"precio": 10.0, "ventas": 100.0},
        {"precio": 12.0, "ventas": 92.0},
        {"precio": 15.0, "ventas": 80.0},
        {"precio": 18.0, "ventas": 70.0},
    ]


@pytest.fixture
def fake_trace() -> dict[str, np.ndarray]:
    return {
        "intercepto": np.array([120.0, 121.5, 119.0, 118.5, 122.0]),
        "pendiente": np.array([-2.4, -2.2, -2.0, -1.9, -2.1]),
        "sigma_ventas": np.array([4.0, 4.2, 3.8, 4.1, 4.3]),
        "beta_1": np.array([-0.6, -0.5, -0.4, -0.3, -0.2]),
        "beta_2": np.array([0.01, 0.02, 0.03, 0.04, 0.05]),
    }


@pytest.fixture
def sample_polynomial_trace() -> dict[str, np.ndarray]:
    return {
        "intercepto": np.array([130.0, 128.0, 132.0, 129.0, 131.0]),
        "beta_1": np.array([-3.0, -2.8, -3.2, -2.9, -3.1]),
        "beta_2": np.array([0.08, 0.07, 0.09, 0.08, 0.07]),
        "sigma_ventas": np.array([4.5, 4.3, 4.6, 4.4, 4.5]),
    }


@pytest.fixture
def patch_sample(monkeypatch, fake_trace):
    optimizer = importlib.import_module("Optimizacion_Precios_PyMC")

    def _apply(trace: dict[str, np.ndarray] | None = None):
        chosen_trace = trace if trace is not None else fake_trace

        def _mock_sample(*args, **kwargs):
            return chosen_trace

        monkeypatch.setattr(optimizer.pm, "sample", _mock_sample)
        return chosen_trace

    return _apply

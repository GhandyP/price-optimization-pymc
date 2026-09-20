from __future__ import annotations

import importlib

import arviz as az
import numpy as np
import pytest


@pytest.fixture
def sample_observations() -> list[dict[str, float]]:
    return [
        {"precio": 10.0, "ventas": 100.0},
        {"precio": 12.0, "ventas": 92.0},
        {"precio": 15.0, "ventas": 80.0},
        {"precio": 18.0, "ventas": 70.0},
    ]


def _trace(samples: dict[str, np.ndarray]) -> az.InferenceData:
    return az.from_dict(posterior={name: values.reshape(2, -1) for name, values in samples.items()})


@pytest.fixture
def fake_trace() -> az.InferenceData:
    return _trace(
        {
            "intercepto": np.array([120.0, 121.5, 119.0, 118.5, 122.0, 120.5, 120.0, 121.5, 119.0, 118.5, 122.0, 120.5]),
            "pendiente": np.array([-2.4, -2.2, -2.0, -1.9, -2.1, -2.3, -2.4, -2.2, -2.0, -1.9, -2.1, -2.3]),
            "sigma_ventas": np.array([4.0, 4.2, 3.8, 4.1, 4.3, 4.1, 4.0, 4.2, 3.8, 4.1, 4.3, 4.1]),
            "beta_1": np.array([-0.6, -0.5, -0.4, -0.3, -0.2, -0.5, -0.6, -0.5, -0.4, -0.3, -0.2, -0.5]),
            "beta_2": np.array([0.01, 0.02, 0.03, 0.04, 0.05, 0.03, 0.01, 0.02, 0.03, 0.04, 0.05, 0.03]),
        }
    )


@pytest.fixture
def sample_polynomial_trace() -> az.InferenceData:
    return _trace(
        {
            "intercepto": np.array([130.0, 128.0, 132.0, 129.0, 131.0, 130.0, 130.0, 128.0, 132.0, 129.0, 131.0, 130.0]),
            "beta_1": np.array([-3.0, -2.8, -3.2, -2.9, -3.1, -3.0, -3.0, -2.8, -3.2, -2.9, -3.1, -3.0]),
            "beta_2": np.array([0.08, 0.07, 0.09, 0.08, 0.07, 0.08, 0.08, 0.07, 0.09, 0.08, 0.07, 0.08]),
            "sigma_ventas": np.array([4.5, 4.3, 4.6, 4.4, 4.5, 4.5, 4.5, 4.3, 4.6, 4.4, 4.5, 4.5]),
        }
    )


@pytest.fixture
def patch_sample(monkeypatch, fake_trace):
    optimizer = importlib.import_module("price_optimizer.model")

    def _apply(trace: az.InferenceData | None = None):
        chosen_trace = trace if trace is not None else fake_trace

        def _mock_sample(*args, **kwargs):
            return chosen_trace

        monkeypatch.setattr(optimizer.pm, "sample", _mock_sample)
        return chosen_trace

    return _apply

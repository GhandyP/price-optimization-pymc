from __future__ import annotations

import json
import time
from importlib.metadata import version

import pytest
from fastapi.testclient import TestClient

from price_optimizer import api
from price_optimizer.model import PriceOptimizationResult

client = TestClient(api.app)
OBSERVATIONS = [{"precio": 10, "ventas": 100}, {"precio": 15, "ventas": 80}, {"precio": 20, "ventas": 60}]


def result() -> PriceOptimizationResult:
    return PriceOptimizationResult(
        price_grid=[10.0, 12.5, 15.0, 17.5, 20.0],
        expected_sales=[100.0, 90.0, 80.0, 70.0, 60.0],
        expected_revenue=[1000.0, 1125.0, 1200.0, 1225.0, 1200.0],
        optimal_price=17.5,
        optimal_expected_revenue=1225.0,
        parameter_means={"intercepto": 120.0, "pendiente": -3.0, "sigma_ventas": 4.0},
        raw_trace={},
        expected_sales_hdi_low=[90.0, 82.0, 74.0, 64.0, 54.0],
        expected_sales_hdi_high=[110.0, 98.0, 86.0, 76.0, 66.0],
        expected_revenue_hdi_low=[900.0, 1025.0, 1100.0, 1125.0, 1100.0],
        expected_revenue_hdi_high=[1100.0, 1225.0, 1300.0, 1325.0, 1300.0],
        diagnostics={
            "rhat": {"intercepto": 1.0},
            "ess": {"intercepto": 200.0},
            "max_rhat": 1.0,
            "min_ess": 200.0,
            "converged": True,
        },
        warnings=["example warning"],
    )


def test_health_returns_contract_and_project_version():
    response = client.get("/health")
    assert response.status_code == 200
    assert set(response.json()) == {"status", "version", "timestamp"}
    assert response.json()["version"] == version("price-optimization-pymc")


def test_optimise_returns_result_without_plot(monkeypatch):
    monkeypatch.setattr(api, "run_price_optimization", lambda *args, **kwargs: result())
    response = client.post("/optimise", json={"observations": OBSERVATIONS})
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "price_grid",
        "expected_sales",
        "expected_revenue",
        "optimal_price",
        "optimal_expected_revenue",
        "parameter_means",
        "model_type",
        "degree",
        "expected_sales_hdi_low",
        "expected_sales_hdi_high",
        "expected_revenue_hdi_low",
        "expected_revenue_hdi_high",
        "diagnostics",
        "warnings",
    }
    for field in (
        "expected_sales_hdi_low",
        "expected_sales_hdi_high",
        "expected_revenue_hdi_low",
        "expected_revenue_hdi_high",
    ):
        assert len(payload[field]) == len(payload["price_grid"])
        assert isinstance(payload[field], list)
        assert all(isinstance(value, (int, float)) for value in payload[field])
    assert set(payload["diagnostics"]) == {"rhat", "ess", "max_rhat", "min_ess", "converged"}
    assert isinstance(payload["diagnostics"], dict)
    assert isinstance(payload["warnings"], list)
    assert all(isinstance(warning, str) for warning in payload["warnings"])
    assert "revenue_plot_base64" not in payload


def test_optimise_serializes_none_diagnostics_as_json_null_without_nan(monkeypatch):
    response_result = result()
    response_result.diagnostics = {
        "rhat": {"intercepto": None},
        "ess": {"intercepto": None},
        "max_rhat": None,
        "min_ess": None,
        "converged": False,
    }
    monkeypatch.setattr(api, "run_price_optimization", lambda *args, **kwargs: response_result)

    response = client.post("/optimise", json={"observations": OBSERVATIONS})

    assert response.status_code == 200
    assert response.json()["diagnostics"] == {
        "rhat": {"intercepto": None},
        "ess": {"intercepto": None},
        "max_rhat": None,
        "min_ess": None,
        "converged": False,
    }
    assert "NaN" not in response.text
    assert "Infinity" not in response.text


def test_optimise_response_is_strict_json(monkeypatch):
    monkeypatch.setattr(api, "run_price_optimization", lambda *args, **kwargs: result())
    response = client.post("/optimise", json={"observations": OBSERVATIONS})

    def reject_constant(value):
        raise AssertionError(f"invalid JSON constant: {value}")

    json.loads(response.text, parse_constant=reject_constant)


def test_optimise_forwards_request_parameters(monkeypatch):
    captured = {}

    def capture(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return result()

    monkeypatch.setattr(api, "run_price_optimization", capture)
    payload = {
        "observations": OBSERVATIONS,
        "draws": 750,
        "tune": 350,
        "target_accept": 0.85,
        "model_type": "polynomial",
        "degree": 2,
    }

    response = client.post("/optimise", json=payload)

    assert response.status_code == 200
    assert captured["args"] == ([dict(observation) for observation in OBSERVATIONS],)
    assert captured["kwargs"] == {
        "price_grid": None,
        "draws": 750,
        "tune": 350,
        "target_accept": 0.85,
        "model_type": "polynomial",
        "degree": 2,
    }


@pytest.mark.parametrize("price_grid", [[0, 1, 2, 3, 4], [-1, 1, 2, 3, 4]])
def test_validation_rejects_non_positive_price_grid(price_grid):
    response = client.post("/optimise", json={"observations": OBSERVATIONS, "price_grid": price_grid})

    assert response.status_code == 422
    assert "Los precios del grid deben ser mayores que cero." in response.text


@pytest.mark.parametrize("invalid_price", [float("nan"), float("inf")])
def test_validation_rejects_non_finite_observation_price(invalid_price):
    observations = [dict(observation) for observation in OBSERVATIONS]
    observations[0]["precio"] = invalid_price

    response = client.post(
        "/optimise",
        content=json.dumps({"observations": observations}),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"observations": OBSERVATIONS[:2]}, "al menos 3"),
        ({"observations": [{"precio": 0, "ventas": 10}] * 3}, "greater than 0"),
        ({"observations": [{"precio": 10, "ventas": -1}] * 3}, "greater than or equal to 0"),
        ({"observations": OBSERVATIONS, "price_grid": [1, 2, 3, 4]}, "al menos cinco"),
        ({"observations": OBSERVATIONS, "draws": 100}, "greater than or equal to 500"),
        ({"observations": OBSERVATIONS, "draws": 10001}, "less than or equal to 10000"),
        ({"observations": OBSERVATIONS, "tune": 100}, "greater than or equal to 200"),
        ({"observations": OBSERVATIONS, "target_accept": 1.5}, "less than or equal to 0.99"),
        ({"observations": OBSERVATIONS, "model_type": "cubica"}, "linear"),
        ({"observations": OBSERVATIONS, "model_type": "polynomial", "degree": 6}, "less than or equal to 5"),
        ({"observations": OBSERVATIONS, "model_type": "polynomial", "degree": 3}, "menor al número"),
    ],
)
def test_validation_returns_422(payload, message):
    response = client.post("/optimise", json=payload)
    assert response.status_code == 422
    assert message in response.text


def test_helper_value_error_returns_400(monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError("boom")

    monkeypatch.setattr(api, "run_price_optimization", fail)
    response = client.post("/optimise", json={"observations": OBSERVATIONS})
    assert response.status_code == 400
    assert response.json()["detail"] == "boom"


def test_helper_timeout_returns_504(monkeypatch):
    def slow(*args, **kwargs):
        time.sleep(0.05)
        return result()

    monkeypatch.setattr(api, "run_price_optimization", slow)
    monkeypatch.setattr(api, "INFERENCE_TIMEOUT_SECONDS", 0.001)
    response = client.post("/optimise", json={"observations": OBSERVATIONS})
    assert response.status_code == 504

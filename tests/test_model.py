from __future__ import annotations

import importlib

import numpy as np
import pandas as pd
import pytest

optimizer = importlib.import_module("price_optimizer.model")


def test_coerce_dataframe_accepts_dataframe_and_coerces_numeric_strings():
    source = pd.DataFrame({"precio": ["10", "12.5"], "ventas": ["20", "25"]})
    result = optimizer._coerce_dataframe(source)
    assert list(result.columns) == ["precio", "ventas"]
    assert result["precio"].dtype.kind in {"f", "i"}
    assert result["ventas"].dtype.kind in {"f", "i"}
    assert result["precio"].tolist() == [10.0, 12.5]
    assert result["ventas"].tolist() == [20, 25]


def test_coerce_dataframe_accepts_iterable_of_mappings():
    rows = ({"precio": price, "ventas": sales} for price, sales in [(10, 100), (15, 85), (20, 60)])
    result = optimizer._coerce_dataframe(rows)
    assert result.shape == (3, 2)
    assert result["precio"].tolist() == [10, 15, 20]
    assert result["ventas"].tolist() == [100, 85, 60]


@pytest.mark.parametrize(
    "invalid_rows,expected_message",
    [([{"precio": 10}], "ventas"), ([{"ventas": 10}], "precio"), ([], "Faltan columnas requeridas")],
)
def test_coerce_dataframe_rejects_missing_columns_or_empty_data(invalid_rows, expected_message):
    with pytest.raises(ValueError, match=expected_message):
        optimizer._coerce_dataframe(invalid_rows)


def test_coerce_dataframe_rejects_empty_dataframe_with_required_columns():
    empty_df = pd.DataFrame({"precio": pd.Series(dtype=float), "ventas": pd.Series(dtype=float)})
    with pytest.raises(ValueError, match="al menos una observacion"):
        optimizer._coerce_dataframe(empty_df)


def test_build_price_grid_uses_custom_grid_when_valid():
    custom_grid = [9, 10, 11, 12, 13]
    result = optimizer._build_price_grid(custom_grid, prices=np.array([10.0, 12.0, 14.0]))
    np.testing.assert_allclose(result, np.array(custom_grid, dtype=float))


def test_build_price_grid_rejects_custom_grid_with_less_than_five_values():
    with pytest.raises(ValueError, match="al menos cinco"):
        optimizer._build_price_grid([10, 11, 12, 13], prices=np.array([10.0, 12.0]))


def test_build_price_grid_auto_generates_uniform_grid_for_single_observation_price():
    grid = optimizer._build_price_grid(None, np.array([15.0]))
    assert len(grid) == 100
    assert grid[0] == pytest.approx(15.0)
    assert grid[-1] == pytest.approx(16.0)


def test_run_price_optimization_with_list_input_returns_result_dataclass(sample_observations, patch_sample):
    patch_sample()
    custom_grid = [9, 10, 11, 12, 13, 14]
    result = optimizer.run_price_optimization(sample_observations, price_grid=custom_grid, draws=10, tune=10)
    assert isinstance(result, optimizer.PriceOptimizationResult)
    assert result.price_grid == [float(value) for value in custom_grid]
    assert len(result.expected_sales) == len(custom_grid)
    assert len(result.expected_revenue) == len(custom_grid)
    assert result.optimal_price in result.price_grid
    assert set(result.parameter_means.keys()) == {"intercepto", "pendiente", "sigma_ventas"}
    assert set(result.raw_trace.keys()) == {"intercepto", "pendiente", "sigma_ventas"}


def test_run_price_optimization_accepts_dataframe_input(sample_observations, patch_sample):
    patch_sample()
    result = optimizer.run_price_optimization(pd.DataFrame(sample_observations), draws=10, tune=10)
    assert isinstance(result, optimizer.PriceOptimizationResult)
    assert len(result.price_grid) == 100
    assert min(result.price_grid) == pytest.approx(10.0)
    assert max(result.price_grid) == pytest.approx(18.0)


def test_run_price_optimization_raises_for_invalid_custom_grid(sample_observations, patch_sample):
    patch_sample()
    with pytest.raises(ValueError, match="al menos cinco"):
        optimizer.run_price_optimization(sample_observations, price_grid=[10, 11, 12, 13], draws=10, tune=10)


@pytest.mark.integration
def test_run_price_optimization_integration_small_dataset():
    observations = [
        {"precio": 9.5, "ventas": 120.0},
        {"precio": 11.0, "ventas": 104.0},
        {"precio": 12.5, "ventas": 91.0},
    ]
    result = optimizer.run_price_optimization(observations, draws=20, tune=20, target_accept=0.8)
    assert isinstance(result, optimizer.PriceOptimizationResult)
    assert len(result.price_grid) == len(result.expected_sales) == len(result.expected_revenue)
    assert result.optimal_expected_revenue == pytest.approx(max(result.expected_revenue))
    assert min(result.price_grid) <= result.optimal_price <= max(result.price_grid)


def test_run_price_optimization_polynomial_returns_beta_parameters(
    sample_observations, patch_sample, sample_polynomial_trace
):
    patch_sample(sample_polynomial_trace)
    result = optimizer.run_price_optimization(
        sample_observations, price_grid=[9, 10, 11, 12, 13, 14], model_type="polynomial", degree=2, draws=10, tune=10
    )
    assert result.model_type == "polynomial"
    assert result.degree == 2
    assert set(result.parameter_means.keys()) == {"intercepto", "beta_1", "beta_2", "sigma_ventas"}
    assert set(result.raw_trace.keys()) == {"intercepto", "beta_1", "beta_2", "sigma_ventas"}
    assert len(result.expected_sales) == 6
    assert len(result.expected_revenue) == 6
    assert result.optimal_price in result.price_grid


def test_run_price_optimization_rejects_invalid_model_type(sample_observations, patch_sample):
    patch_sample()
    with pytest.raises(ValueError, match="model_type"):
        optimizer.run_price_optimization(sample_observations, model_type="cubica", draws=10, tune=10)


def test_run_price_optimization_rejects_degree_too_high_for_observations(patch_sample):
    patch_sample()
    observations = [{"precio": 10.0, "ventas": 100.0}, {"precio": 15.0, "ventas": 80.0}, {"precio": 20.0, "ventas": 60.0}]
    with pytest.raises(ValueError, match="menor al número de observaciones"):
        optimizer.run_price_optimization(observations, model_type="polynomial", degree=3, draws=10, tune=10)

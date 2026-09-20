from __future__ import annotations

import importlib
import json
import warnings

import arviz as az
import numpy as np
import pandas as pd
import pytest

optimizer = importlib.import_module("price_optimizer.model")


def test_data_scale_is_positive_for_degenerate_values():
    assert optimizer._data_scale(np.array([5.0, 5.0])) == pytest.approx(0.5)
    assert optimizer._data_scale(np.zeros(3)) == pytest.approx(1.0)


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


def test_run_price_optimization_passes_four_chains_to_sampler(sample_observations, patch_sample, monkeypatch):
    trace = patch_sample()
    captured = {}

    def capture_sample(*args, **kwargs):
        captured.update(kwargs)
        return trace

    monkeypatch.setattr(optimizer.pm, "sample", capture_sample)
    optimizer.run_price_optimization(sample_observations, draws=10, tune=10)

    assert captured["chains"] == 4
    assert captured["progressbar"] is False


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
    convergence_warning = any("converg" in warning.lower() for warning in result.warnings)
    assert convergence_warning is (not result.diagnostics["converged"])
    assert len(result.price_grid) == len(result.expected_sales) == len(result.expected_revenue)
    assert result.optimal_expected_revenue == pytest.approx(max(result.expected_revenue))
    assert min(result.price_grid) <= result.optimal_price <= max(result.price_grid)


def test_result_contains_hdi_and_convergence_diagnostics(sample_observations, patch_sample):
    rng = np.random.default_rng(0)
    well_behaved_trace = az.from_dict(
        posterior={
            "intercepto": rng.normal(120.0, 0.5, (2, 100)),
            "pendiente": rng.normal(-2.1, 0.05, (2, 100)),
            "sigma_ventas": rng.normal(4.0, 0.1, (2, 100)),
        }
    )
    patch_sample(well_behaved_trace)
    result = optimizer.run_price_optimization(sample_observations, price_grid=[9, 10, 11, 12, 13, 14], draws=10, tune=10)
    assert len(result.expected_sales_hdi_low) == len(result.price_grid)
    assert len(result.expected_revenue_hdi_low) == len(result.price_grid)
    assert all(low <= mean <= high for low, mean, high in zip(result.expected_sales_hdi_low, result.expected_sales, result.expected_sales_hdi_high))
    assert set(result.diagnostics) == {"rhat", "ess", "max_rhat", "min_ess", "converged"}
    assert result.diagnostics["converged"] is True


def test_single_chain_diagnostics_are_none_and_strict_json_safe(sample_observations, patch_sample):
    single_chain_trace = az.from_dict(
        posterior={
            "intercepto": np.full((1, 6), 120.0),
            "pendiente": np.full((1, 6), -2.1),
            "sigma_ventas": np.full((1, 6), 4.0),
        }
    )
    patch_sample(single_chain_trace)

    result = optimizer.run_price_optimization(
        sample_observations, price_grid=[9, 10, 11, 12, 13, 14], draws=10, tune=10
    )
    diagnostics = result.diagnostics
    serialized = json.dumps(diagnostics)

    assert set(diagnostics["rhat"].values()) == {None}
    assert diagnostics["max_rhat"] is None
    assert diagnostics["converged"] is False
    assert "No se pudo evaluar R-hat (se necesitan al menos 2 cadenas)." in result.warnings
    assert "NaN" not in serialized
    assert json.loads(serialized) == diagnostics


def test_hdi_matches_independent_one_dimensional_grid_columns(sample_observations, patch_sample):
    rng = np.random.default_rng(0)
    well_behaved_trace = az.from_dict(
        posterior={
            "intercepto": rng.normal(120.0, 0.5, (2, 100)),
            "pendiente": rng.normal(-2.1, 0.05, (2, 100)),
            "sigma_ventas": rng.normal(4.0, 0.1, (2, 100)),
        }
    )
    patch_sample(well_behaved_trace)
    price_grid = np.array([9, 10, 11, 12, 13, 14], dtype=float)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = optimizer.run_price_optimization(sample_observations, price_grid=price_grid, draws=10, tune=10)

    assert not any("hdi" in str(item.message).lower() and "2d" in str(item.message).lower() for item in caught)

    intercepto = well_behaved_trace.posterior["intercepto"].values
    pendiente = well_behaved_trace.posterior["pendiente"].values
    draw_sales = np.clip(intercepto[:, :, None] + pendiente[:, :, None] * (price_grid - np.mean([10, 12, 15, 18])), 0.0, None)
    for index in (1, 4):
        one_column = draw_sales[:, :, index].reshape(-1)
        expected_interval = np.asarray(az.hdi(one_column, hdi_prob=optimizer.HDI_PROB))
        assert result.expected_sales_hdi_low[index] == pytest.approx(expected_interval[0])
        assert result.expected_sales_hdi_high[index] == pytest.approx(expected_interval[1])


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_badly_mixed_trace_is_not_converged(sample_observations, patch_sample):
    bad_trace = az.from_dict(
        posterior={
            "intercepto": np.array([[100.0] * 6, [200.0] * 6]),
            "pendiente": np.array([[-2.0] * 6, [2.0] * 6]),
            "sigma_ventas": np.array([[4.0] * 6, [20.0] * 6]),
        }
    )
    patch_sample(bad_trace)
    # ArviZ warns while computing diagnostics for this intentionally degenerate trace.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        result = optimizer.run_price_optimization(sample_observations, price_grid=[9, 10, 11, 12, 13, 14], draws=10, tune=10)
    assert result.diagnostics["converged"] is False
    assert any("R-hat" in warning or "muestras efectivas" in warning for warning in result.warnings)


# These fixtures intentionally have zero within-chain variance for diagnostics.
@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_polynomial_draws_are_clipped_before_means_and_revenue(sample_observations, patch_sample):
    trace = az.from_dict(
        posterior={
            "intercepto": np.zeros((2, 6)),
            "beta_1": np.full((2, 6), -1.0),
            "beta_2": np.zeros((2, 6)),
            "sigma_ventas": np.full((2, 6), 2.0),
        }
    )
    patch_sample(trace)
    result = optimizer.run_price_optimization(
        sample_observations, price_grid=[9, 10, 11, 12, 13, 14], model_type="polynomial", degree=2, draws=10, tune=10
    )
    assert min(result.expected_sales) == 0.0
    assert result.expected_revenue == pytest.approx(np.array(result.price_grid) * result.expected_sales)
    assert "Se recortaron ventas esperadas negativas en 1 punto(s) del grid." in result.warnings


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_boundary_warning_only_applies_at_grid_edge(sample_observations, patch_sample):
    patch_sample()
    edge = optimizer.run_price_optimization(sample_observations, price_grid=[9, 10, 11, 12, 13, 14], draws=10, tune=10)
    assert any("borde del grid" in warning for warning in edge.warnings)
    interior_trace = az.from_dict(
        posterior={
            "intercepto": np.full((2, 6), 100.0),
            "beta_1": np.full((2, 6), -15.0),
            "beta_2": np.zeros((2, 6)),
            "sigma_ventas": np.full((2, 6), 2.0),
        }
    )
    patch_sample(interior_trace)
    interior = optimizer.run_price_optimization(
        sample_observations, price_grid=[9, 10, 11, 12, 13, 14], model_type="polynomial", degree=2, draws=10, tune=10
    )
    assert not any("borde del grid" in warning for warning in interior.warnings)


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

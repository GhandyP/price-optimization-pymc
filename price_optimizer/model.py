"""Reusable PyMC model to estimate optimal pricing under linear or polynomial demand."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

import arviz as az
import numpy as np
import pandas as pd
import pymc as pm
import xarray as xr

REQUIRED_COLUMNS = {"precio", "ventas"}
HDI_PROB = 0.9
MAX_RHAT = 1.01
MIN_ESS = 100.0


@dataclass
class PriceOptimizationResult:
    price_grid: list[float]
    expected_sales: list[float]
    expected_revenue: list[float]
    optimal_price: float
    optimal_expected_revenue: float
    parameter_means: dict[str, float]
    raw_trace: dict
    model_type: str = "linear"
    degree: int = 2
    expected_sales_hdi_low: list[float] = field(default_factory=list)
    expected_sales_hdi_high: list[float] = field(default_factory=list)
    expected_revenue_hdi_low: list[float] = field(default_factory=list)
    expected_revenue_hdi_high: list[float] = field(default_factory=list)
    diagnostics: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _data_scale(values: np.ndarray) -> float:
    """Positive spread of the data, safe for degenerate inputs."""
    spread = float(np.std(values))
    if spread > 0:
        return spread
    level = abs(float(np.mean(values)))
    return level * 0.1 if level > 0 else 1.0


def _posterior_samples(trace, parameter: str) -> np.ndarray:
    return np.asarray(trace.posterior[parameter].values, dtype=float).reshape(-1)


def _posterior_chain_draw_samples(trace, parameter: str) -> np.ndarray:
    """Return posterior samples with explicit ``(chain, draw)`` axes."""
    return np.asarray(trace.posterior[parameter].values, dtype=float)


def _finite_or_none(value: float) -> float | None:
    return float(value) if np.isfinite(value) else None


def run_price_optimization(
    observations: Sequence[Mapping[str, float]] | pd.DataFrame | Iterable[Mapping[str, float]],
    *,
    price_grid: Sequence[float] | None = None,
    draws: int = 2000,
    tune: int = 1000,
    target_accept: float = 0.9,
    model_type: str = "linear",
    degree: int = 2,
) -> PriceOptimizationResult:
    """Fit a price-demand model and identify the revenue-maximising price.

    ``model_type="linear"`` (default) fits the classic linear regression
    ``ventas ~ precio``; ``model_type="polynomial"`` fits a polynomial
    regression ``ventas ~ precio + ... + precio^degree`` to capture
    non-linear demand. Prices are centred on their observed mean, so
    ``intercepto`` is expected sales at the average observed price rather
    than at price zero. The ``degree`` is validated against the number of
    observations to avoid overfitting.
    """

    df = _coerce_dataframe(observations)
    prices = df["precio"].to_numpy(dtype=float)
    sales = df["ventas"].to_numpy(dtype=float)

    if model_type not in {"linear", "polynomial"}:
        raise ValueError(f"model_type debe ser 'linear' o 'polynomial', se recibió '{model_type}'.")
    if not isinstance(degree, int) or isinstance(degree, bool) or degree < 1:
        raise ValueError("degree debe ser un entero mayor o igual a 1.")
    if model_type == "polynomial" and degree >= len(df):
        raise ValueError(
            f"degree ({degree}) debe ser menor al número de observaciones ({len(df)}) para evitar sobreajuste."
        )

    prices_centrados = prices - prices.mean()
    escala_ventas = _data_scale(sales)
    escala_precio = _data_scale(prices)

    with pm.Model():
        intercepto = pm.Normal("intercepto", mu=float(sales.mean()), sigma=2 * escala_ventas)

        if model_type == "linear":
            pendiente = pm.Normal("pendiente", mu=0.0, sigma=3 * escala_ventas / escala_precio)
            sigma_ventas = pm.HalfNormal("sigma_ventas", sigma=escala_ventas)
            mu_ventas = intercepto + pendiente * prices_centrados
        else:
            betas = [
                pm.Normal(f"beta_{k}", mu=0.0, sigma=3 * escala_ventas / escala_precio**k)
                for k in range(1, degree + 1)
            ]
            sigma_ventas = pm.HalfNormal("sigma_ventas", sigma=escala_ventas)
            mu_ventas = intercepto + sum(beta * prices_centrados**k for k, beta in enumerate(betas, start=1))

        pm.Normal("ventas_observadas", mu=mu_ventas, sigma=sigma_ventas, observed=sales)
        trace = pm.sample(chains=4, draws=draws, tune=tune, target_accept=target_accept, progressbar=False)

    price_grid_np = _build_price_grid(price_grid, prices)
    intercepto_samples = _posterior_chain_draw_samples(trace, "intercepto")
    grid_centrado = price_grid_np - prices.mean()
    if model_type == "linear":
        unclipped_draw_sales = (
            intercepto_samples[:, :, None]
            + _posterior_chain_draw_samples(trace, "pendiente")[:, :, None] * grid_centrado
        )
    else:
        unclipped_draw_sales = intercepto_samples[:, :, None] + sum(
            _posterior_chain_draw_samples(trace, f"beta_{k}")[:, :, None] * grid_centrado**k
            for k in range(1, degree + 1)
        )
    raw_mean = unclipped_draw_sales.mean(axis=(0, 1))
    clipped_points = int(np.count_nonzero(raw_mean < 0))
    draw_sales = np.clip(unclipped_draw_sales, 0.0, None)
    expected_sales = draw_sales.mean(axis=(0, 1))
    draw_revenue = price_grid_np[None, None, :] * draw_sales
    expected_revenue = draw_revenue.mean(axis=(0, 1))
    sales_hdi = revenue_hdi = None
    try:
        sales_samples = xr.DataArray(draw_sales, dims=("chain", "draw", "grid"))
        revenue_samples = xr.DataArray(draw_revenue, dims=("chain", "draw", "grid"))
        sales_hdi = az.hdi(sales_samples, hdi_prob=HDI_PROB).to_array().values[0]
        revenue_hdi = az.hdi(revenue_samples, hdi_prob=HDI_PROB).to_array().values[0]
    except Exception:  # noqa: BLE001 - interval failures must not discard valid results
        sales_hdi = revenue_hdi = None

    diagnostics = {}
    try:
        rhat_dataset = az.rhat(trace)
        ess_dataset = az.ess(trace)
        rhat = {name: _finite_or_none(float(rhat_dataset[name].values)) for name in parameter_names_from_trace(trace)}
        ess = {name: _finite_or_none(float(ess_dataset[name].values)) for name in parameter_names_from_trace(trace)}
        max_rhat = max((value for value in rhat.values() if value is not None), default=None)
        min_ess = min((value for value in ess.values() if value is not None), default=None)
        converged = (
            all(value is not None and value <= MAX_RHAT for value in rhat.values())
            and all(value is not None and value >= MIN_ESS for value in ess.values())
        )
        diagnostics = {
            "rhat": rhat,
            "ess": ess,
            "max_rhat": max_rhat,
            "min_ess": min_ess,
            "converged": converged,
        }
    except Exception:  # noqa: BLE001 - diagnostic failures must not discard valid results
        diagnostics = {}

    optimal_index = int(np.argmax(expected_revenue))
    optimal_price = float(price_grid_np[optimal_index])
    optimal_expected_revenue = float(expected_revenue[optimal_index])

    parameter_names = ["intercepto"]
    if model_type == "linear":
        parameter_names.append("pendiente")
    else:
        parameter_names.extend(f"beta_{k}" for k in range(1, degree + 1))
    parameter_names.append("sigma_ventas")
    parameter_means = {name: float(_posterior_samples(trace, name).mean()) for name in parameter_names}
    raw_trace = {name: _posterior_samples(trace, name).tolist() for name in parameter_names}

    warnings = []
    if optimal_index in {0, len(price_grid_np) - 1}:
        warnings.append("El precio óptimo cayó en el borde del grid: podría existir un óptimo mayor fuera del rango evaluado.")
    if clipped_points:
        warnings.append(f"Se recortaron ventas esperadas negativas en {clipped_points} punto(s) del grid.")
    if sales_hdi is None or revenue_hdi is None:
        warnings.append("No se pudieron calcular los intervalos de incertidumbre.")
    if not diagnostics:
        warnings.append("No se pudo evaluar la convergencia.")
    elif any(value is None for value in rhat.values()):
        warnings.append("No se pudo evaluar R-hat (se necesitan al menos 2 cadenas).")
    elif max_rhat > MAX_RHAT:
        warnings.append(f"No convergió: R-hat máximo {max_rhat:.3f} (umbral 1.01). Subí draws/tune o target_accept.")
    if diagnostics and min_ess is not None and min_ess < MIN_ESS:
        warnings.append(f"Pocas muestras efectivas: ESS mínimo {min_ess:.0f} (umbral 100).")

    return PriceOptimizationResult(
        price_grid=price_grid_np.tolist(),
        expected_sales=expected_sales.tolist(),
        expected_revenue=expected_revenue.tolist(),
        optimal_price=optimal_price,
        optimal_expected_revenue=optimal_expected_revenue,
        parameter_means=parameter_means,
        raw_trace=raw_trace,
        model_type=model_type,
        degree=degree,
        expected_sales_hdi_low=[] if sales_hdi is None else sales_hdi[:, 0].tolist(),
        expected_sales_hdi_high=[] if sales_hdi is None else sales_hdi[:, 1].tolist(),
        expected_revenue_hdi_low=[] if revenue_hdi is None else revenue_hdi[:, 0].tolist(),
        expected_revenue_hdi_high=[] if revenue_hdi is None else revenue_hdi[:, 1].tolist(),
        diagnostics=diagnostics,
        warnings=warnings,
    )


def parameter_names_from_trace(trace) -> list[str]:
    """Return posterior variable names for convergence diagnostics."""
    return list(trace.posterior.data_vars)


def _coerce_dataframe(
    data: Sequence[Mapping[str, float]] | pd.DataFrame | Iterable[Mapping[str, float]]
) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        df = data.copy()
    else:
        df = pd.DataFrame(list(data))

    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(sorted(missing))}.")
    if df.empty:
        raise ValueError("Debe proporcionar al menos una observacion.")

    for column in REQUIRED_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="raise")

    return df


def _build_price_grid(grid: Sequence[float] | None, prices: np.ndarray) -> np.ndarray:
    if grid is not None:
        array = np.asarray(list(grid), dtype=float)
        if array.ndim != 1 or array.size < 5:
            raise ValueError("price_grid debe tener al menos cinco valores.")
        return array

    min_price = float(prices.min())
    max_price = float(prices.max())
    if np.isclose(min_price, max_price):
        max_price = min_price + 1.0
    return np.linspace(min_price, max_price, num=100)

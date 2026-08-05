"""Reusable PyMC model to estimate optimal pricing under linear or polynomial demand."""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pymc as pm

REQUIRED_COLUMNS = {"precio", "ventas"}


@dataclass
class PriceOptimizationResult:
    price_grid: list[float]
    expected_sales: list[float]
    expected_revenue: list[float]
    optimal_price: float
    optimal_expected_revenue: float
    parameter_means: dict[str, float]
    revenue_plot_base64: str
    raw_trace: dict
    model_type: str = "linear"
    degree: int = 2


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
    non-linear demand. The ``degree`` is validated against the number of
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

    with pm.Model() as model:
        intercepto = pm.Normal("intercepto", mu=float(sales.max()), sigma=max(float(sales.std()), 10.0))

        if model_type == "linear":
            pendiente = pm.Normal("pendiente", mu=-1.0, sigma=1.0)
            sigma_ventas = pm.HalfNormal("sigma_ventas", sigma=max(float(sales.std()), 5.0))
            mu_ventas = intercepto + pendiente * prices
        else:
            betas = [pm.Normal(f"beta_{k}", mu=0.0, sigma=1.0) for k in range(1, degree + 1)]
            sigma_ventas = pm.HalfNormal("sigma_ventas", sigma=max(float(sales.std()), 5.0))
            mu_ventas = intercepto + sum(beta * prices**k for k, beta in enumerate(betas, start=1))

        pm.Normal("ventas_observadas", mu=mu_ventas, sigma=sigma_ventas, observed=sales)

        trace = pm.sample(
            draws=draws,
            tune=tune,
            target_accept=target_accept,
            progressbar=False,
            return_inferencedata=False,
        )

    price_grid_np = _build_price_grid(price_grid, prices)
    if model_type == "linear":
        expected_sales = (trace["intercepto"][:, None] + trace["pendiente"][:, None] * price_grid_np).mean(axis=0)
    else:
        expected_sales = (
            trace["intercepto"][:, None]
            + sum(trace[f"beta_{k}"][:, None] * price_grid_np**k for k in range(1, degree + 1))
        ).mean(axis=0)
    expected_revenue = price_grid_np * expected_sales

    optimal_index = int(np.argmax(expected_revenue))
    optimal_price = float(price_grid_np[optimal_index])
    optimal_expected_revenue = float(expected_revenue[optimal_index])

    if model_type == "linear":
        parameter_means = {
            "intercepto": float(trace["intercepto"].mean()),
            "pendiente": float(trace["pendiente"].mean()),
            "sigma_ventas": float(trace["sigma_ventas"].mean()),
        }
    else:
        parameter_means = {"intercepto": float(trace["intercepto"].mean())}
        for k in range(1, degree + 1):
            parameter_means[f"beta_{k}"] = float(trace[f"beta_{k}"].mean())
        parameter_means["sigma_ventas"] = float(trace["sigma_ventas"].mean())

    revenue_plot_base64 = _encode_plot(
        price_grid_np,
        expected_revenue,
        observed_prices=prices,
        observed_revenue=prices * sales,
        optimal_price=optimal_price,
        optimal_revenue=optimal_expected_revenue,
    )

    if model_type == "linear":
        raw_trace = {
            "intercepto": trace["intercepto"].tolist(),
            "pendiente": trace["pendiente"].tolist(),
            "sigma_ventas": trace["sigma_ventas"].tolist(),
        }
    else:
        raw_trace = {"intercepto": trace["intercepto"].tolist()}
        for k in range(1, degree + 1):
            raw_trace[f"beta_{k}"] = trace[f"beta_{k}"].tolist()
        raw_trace["sigma_ventas"] = trace["sigma_ventas"].tolist()

    return PriceOptimizationResult(
        price_grid=price_grid_np.tolist(),
        expected_sales=expected_sales.tolist(),
        expected_revenue=expected_revenue.tolist(),
        optimal_price=optimal_price,
        optimal_expected_revenue=optimal_expected_revenue,
        parameter_means=parameter_means,
        revenue_plot_base64=revenue_plot_base64,
        raw_trace=raw_trace,
        model_type=model_type,
        degree=degree,
    )


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


def _encode_plot(
    price_grid: np.ndarray,
    expected_revenue: np.ndarray,
    *,
    observed_prices: np.ndarray,
    observed_revenue: np.ndarray,
    optimal_price: float,
    optimal_revenue: float,
) -> str:
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(price_grid, expected_revenue, label="Ingresos esperados", color="steelblue")
    ax.scatter(observed_prices, observed_revenue, color="seagreen", alpha=0.6, label="Datos observados")
    ax.axvline(optimal_price, color="firebrick", linestyle="dashed", label=f"Precio óptimo = {optimal_price:.2f}")
    ax.set_title("Ingresos esperados por precio")
    ax.set_xlabel("Precio")
    ax.set_ylabel("Ingresos")
    ax.legend()

    buffer = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buffer, format="png")
    plt.close(fig)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("ascii")


if __name__ == "__main__":
    sample_data = [
        {"precio": 10, "ventas": 100},
        {"precio": 15, "ventas": 80},
        {"precio": 20, "ventas": 65},
    ]
    result = run_price_optimization(sample_data)
    print("Precio óptimo:", result.optimal_price)

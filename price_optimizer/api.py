"""FastAPI backend exposing the price optimisation PyMC helper."""

from __future__ import annotations

import asyncio
import logging
import math
import time
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from price_optimizer.model import run_price_optimization

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
INFERENCE_TIMEOUT_SECONDS = 120.0

try:
    PACKAGE_VERSION = version("price-optimization-pymc")
except PackageNotFoundError:
    PACKAGE_VERSION = "unknown"

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Optimizacion de Precios",
    version=PACKAGE_VERSION,
    description="API que estima elasticidad y precio óptimo maximizando ingresos con PyMC.",
)


def _json_safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, BaseException):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": _json_safe(exc.errors())})


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = (time.time() - start_time) * 1000
    logger.info(f"{request.method} {request.url.path} {response.status_code} {duration:.2f}ms")
    return response


class PriceObservation(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    precio: float = Field(..., gt=0)
    ventas: float = Field(..., ge=0)


class PriceOptimisationRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    observations: list[PriceObservation]
    price_grid: list[Annotated[float, Field(allow_inf_nan=False)]] | None = None
    draws: int = Field(2000, ge=500, le=10000)
    tune: int = Field(1000, ge=200, le=10000)
    target_accept: Annotated[float, Field(ge=0.5, le=0.99, allow_inf_nan=False)] = 0.9
    model_type: str = "linear"
    degree: int = Field(2, ge=1, le=5)

    @field_validator("observations")
    @classmethod
    def _validate_observations(cls, value: list[PriceObservation]) -> list[PriceObservation]:
        if len(value) < 3:
            raise ValueError("Debe proporcionar al menos 3 observaciones de precio-venta.")
        return value

    @field_validator("price_grid")
    @classmethod
    def _validate_price_grid(cls, value):
        if value is not None and len(value) < 5:
            raise ValueError("price_grid debe tener al menos cinco valores.")
        if value is not None and any(price <= 0 for price in value):
            raise ValueError("Los precios del grid deben ser mayores que cero.")
        return value

    @field_validator("model_type")
    @classmethod
    def _validate_model_type(cls, value: str) -> str:
        if value not in {"linear", "polynomial"}:
            raise ValueError("model_type debe ser 'linear' o 'polynomial'.")
        return value

    @model_validator(mode="after")
    def _validate_polynomial_degree(self):
        if self.model_type == "polynomial" and self.degree >= len(self.observations):
            raise ValueError(
                f"degree ({self.degree}) debe ser menor al número de observaciones ({len(self.observations)}) para evitar sobreajuste."
            )
        return self


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", summary="Interfaz web de optimización")
async def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", summary="Health check")
async def health() -> dict:
    return {"status": "ok", "version": PACKAGE_VERSION, "timestamp": datetime.now(UTC).isoformat()}


@app.post("/optimise", summary="Calcula precio óptimo y métricas asociadas")
async def optimise(request: PriceOptimisationRequest) -> dict:
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                run_price_optimization,
                [obs.model_dump() for obs in request.observations],
                price_grid=request.price_grid,
                draws=request.draws,
                tune=request.tune,
                target_accept=request.target_accept,
                model_type=request.model_type,
                degree=request.degree,
            ),
            timeout=INFERENCE_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Inference timed out")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "price_grid": result.price_grid,
        "expected_sales": result.expected_sales,
        "expected_revenue": result.expected_revenue,
        "optimal_price": result.optimal_price,
        "optimal_expected_revenue": result.optimal_expected_revenue,
        "parameter_means": result.parameter_means,
        "model_type": result.model_type,
        "degree": result.degree,
    }

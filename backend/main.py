"""FastAPI backend exposing the price optimisation PyMC helper."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parents[1]
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

from Optimizacion_Precios_PyMC import run_price_optimization

app = FastAPI(
    title="Optimizacion de Precios",
    version="1.0.0",
    description="API que estima elasticidad y precio óptimo maximizando ingresos con PyMC.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = (time.time() - start_time) * 1000
    logger.info(f"{request.method} {request.url.path} {response.status_code} {duration:.2f}ms")
    return response


class PriceObservation(BaseModel):
    precio: float = Field(..., gt=0)
    ventas: float = Field(..., ge=0)


class PriceOptimisationRequest(BaseModel):
    observations: List[PriceObservation]
    price_grid: Optional[List[float]] = None
    draws: int = Field(2000, ge=500, le=10000)
    tune: int = Field(1000, ge=200, le=10000)
    target_accept: float = Field(0.9, ge=0.5, le=0.99)
    model_type: str = "linear"
    degree: int = Field(2, ge=1, le=5)

    @validator("observations")
    def _validate_observations(cls, value: List[PriceObservation]) -> List[PriceObservation]:
        if len(value) < 3:
            raise ValueError("Debe proporcionar al menos 3 observaciones de precio-venta.")
        return value

    @validator("model_type")
    def _validate_model_type(cls, value: str) -> str:
        if value not in {"linear", "polynomial"}:
            raise ValueError("model_type debe ser 'linear' o 'polynomial'.")
        return value


@app.get("/", summary="Estado del servicio")
async def root() -> dict:
    return {"status": "ok"}


@app.get("/health", summary="Health check")
async def health() -> dict:
    return {
        "status": "ok",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/optimise", summary="Calcula precio óptimo y métricas asociadas")
async def optimise(request: PriceOptimisationRequest) -> dict:
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                run_price_optimization,
                [obs.dict() for obs in request.observations],
                price_grid=request.price_grid,
                draws=request.draws,
                tune=request.tune,
                target_accept=request.target_accept,
                model_type=request.model_type,
                degree=request.degree,
            ),
            timeout=120.0,
        )
    except asyncio.TimeoutError:
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
        "revenue_plot_base64": result.revenue_plot_base64,
        "model_type": result.model_type,
        "degree": result.degree,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)

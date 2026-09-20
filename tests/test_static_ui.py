from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from price_optimizer.api import app

client = TestClient(app)
STATIC_DIR = Path(__file__).parents[1] / "price_optimizer" / "static"


def test_root_serves_expected_html():
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Optimización de Precios · PyMC" in response.text
    assert 'id="optimisation-form"' in response.text
    assert "Datos históricos (precio, ventas)" in response.text


def test_static_assets_are_served():
    assert client.get("/static/styles.css").headers["content-type"].startswith("text/css")
    assert client.get("/static/app.js").headers["content-type"].startswith("text/javascript")
    assert client.get("/static/favicon.svg").status_code == 200


def test_javascript_element_lookups_exist_in_html():
    html = (STATIC_DIR / "index.html").read_text()
    javascript = (STATIC_DIR / "app.js").read_text()
    html_ids = set(re.findall(r'id="([^"]+)"', html))
    looked_up = set(re.findall(r'getElementById\("([^"]+)"\)', javascript))
    looked_up.update(re.findall(r'querySelector\("#([^" ]+)"\)', javascript))
    assert looked_up <= html_ids
    assert '/static/styles.css' in html
    assert '/static/app.js' in html


def test_javascript_consumes_uncertainty_diagnostics_and_warnings():
    javascript = (STATIC_DIR / "app.js").read_text()
    for field in ("expected_revenue_hdi_low", "expected_revenue_hdi_high", "diagnostics", "warnings"):
        assert field in javascript


def test_static_assets_do_not_reference_external_hosts():
    html = (STATIC_DIR / "index.html").read_text()
    javascript = (STATIC_DIR / "app.js").read_text()

    asset_references = re.findall(r'(?:src|href)="([^"]+)"', html)
    assert asset_references, "index.html should reference its own assets"
    assert all(reference.startswith("/") for reference in asset_references)

    assert not re.search(r"""fetch\(\s*["']https?:""", javascript)
    assert not re.search(r"""(?:src|href)\s*:\s*["']https?:""", javascript)

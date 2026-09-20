# ODD · Reemplazo de Flutter por una UI web servida por FastAPI

**Estado:** ✅ cerrada el 2026-09-17 · **Review nativo:** aprobado y reconocido (linaje
`review-11e8f9041397401b`) · **Commits y publicación:** ver `odd/tasks/publish-and-protect.md`

## Objetivo

Reemplazar la app Flutter por una interfaz web servida por el propio backend, con un entorno
reproducible de un solo comando, de modo que el proyecto se pueda **correr, probar y mostrar** sin
toolchain de frontend.

Resultado esperado:

```bash
uv sync
uv run price-opt        # levanta el backend y abre el navegador
uv run pytest -q        # suite rápida (sin sampler real)
```

## No objetivos (fuera de alcance)

- Calibración del modelo: prior del slope (`Normal(-1, 1)`), guard de óptimo en el borde del grid,
  clip de ventas negativas, intervalos de credibilidad, R-hat/ESS. → feature siguiente.
- Dockerfile, CI, cola de trabajos, autenticación, persistencia.
- Commitear o publicar: se decide al final de la feature, con el usuario.

## Decisiones cerradas

| # | Decisión | Motivo |
|---|----------|--------|
| D1 | UI = HTML/CSS/JS propio servido por FastAPI, sin CDN ni build step | Un solo proceso y un solo comando; gráfico SVG a mano desde el JSON del endpoint |
| D2 | Se borra `flutter_app/` | Un único frontend; la historia queda en git |
| D3 | Alcance = UI + entorno reproducible + tests de la capa HTTP | Es lo que habilita "fácil de probar y mostrar" sin inflar la revisión |
| D4 | Paquete instalable `price_optimizer/` con `pyproject.toml` y entry point `price-opt` | Mata el hack `sys.path.insert` y el módulo con mayúsculas en la raíz |
| D5 | Se elimina `matplotlib` y el `revenue_plot_base64` | El gráfico lo dibuja el navegador: depende menos, responde mejor y el JSON pesa menos |
| D6 | Se elimina CORS y `flutter_dotenv`/`.env` | Un solo origen: el cliente y la API salen del mismo servidor |
| D7 | Entorno con `uv` + `.python-version` = 3.11 y `uv.lock` versionado | El `python3` del sistema (3.13, sin `ensurepip`) no puede crear venvs ni correr los pins actuales |
| D8 | PyMC pasa a `return_inferencedata` por defecto (`InferenceData`) | `return_inferencedata=False` está deprecado y rompe en la próxima major |
| D9 | Idioma: se mantiene la convención del repo (docs y copy en español, identificadores de dominio en español, estructura de código en inglés) | No romper el contrato `precio`/`ventas` ni reescribir documentación por gusto |
| D10 | `GET /` pasa a servir la UI; el estado JSON queda en `GET /health` | Cambio de contrato documentado en el README |

## Unidades de trabajo

### WU1 · Backend como paquete instalable + entorno uv + tests migrados ✅

- [x] **T1** `pyproject.toml` (PEP 621) + `.python-version`: deps de runtime (`pymc>=5.16,<6`,
  `numpy>=1.26`, `pandas>=2.2`, `fastapi>=0.115`, `uvicorn>=0.32`), grupo `dev` (`pytest`, `httpx`,
  `ruff`), `[project.scripts] price-opt`, config de pytest en `[tool.pytest.ini_options]`
  (excluye `integration` por defecto), ruff `line-length = 120`.
  Fallback si falla la resolución: `pymc==5.16.0` + `numpy==1.26.0`.
- [x] **T2** `price_optimizer/model.py`: porte del helper PyMC. Sin `matplotlib`, sin
  `_encode_plot`, sin el campo `revenue_plot_base64`, sin el bloque `__main__`. Sampling con
  `InferenceData` (D8) y aplanado `(chain, draw) → 1-D`. **Priors intactos** (van a la feature de
  calibración).
- [x] **T3** `price_optimizer/api.py`: porte de `backend/main.py`. Pydantic v2
  (`field_validator`, `model_validator`, `model_dump`), sin CORS. El contrato de entrada queda
  validado en la capa HTTP: observaciones ≥ 3 y finitas, `price_grid` ≥ 5 y finito, `draws`
  500–10000, `tune` 200–10000, `target_accept` 0.5–0.99, `degree` 1–5 y `< len(observations)`.
  `INFERENCE_TIMEOUT_SECONDS` como constante de módulo (testeable), timeout 120 s → 504.
- [x] **T4** `price_optimizer/cli.py`: entry point `price-opt` con `argparse` (`--host`, `--port`,
  `--no-open`), levanta uvicorn y abre el navegador.
- [x] **T5** Tests: `tests/conftest.py` (se elimina el módulo PyMC falso: era un falso verde),
  `tests/test_model.py` migrado desde `backend/tests/` sin las aserciones de PNG. Se borran
  `backend/`, `pytest.ini` y el módulo raíz viejo `Optimizacion_Precios_PyMC.py`.

**Superficies de escritura WU1:** `pyproject.toml`, `.python-version`, `price_optimizer/**`,
`tests/**`. Puede borrar: `backend/`, `pytest.ini`, `Optimizacion_Precios_PyMC.py`.

**DoD WU1:** ✅ `uv sync` resuelve (65 paquetes, sin fallback de pins), `uv run pytest -q` = 15 passed + 1 integración excluida,
`uv run pytest -q -m integration` = sampler real OK, `uv run ruff check .` limpio, `uv run price-opt --help` OK.

### WU2 · UI web sin build step ✅

- [x] **T6** `tests/test_api.py`: capa HTTP completa — `GET /health`, `POST /optimise` happy path
  (con `run_price_optimization` monkeypatcheado), cada validación (422), `ValueError` del helper
  (400), timeout (504).
- [x] **T7** `price_optimizer/static/{index.html,styles.css,app.js}`: formulario, validación espejo
  de los límites del backend, gráfico SVG (línea de ingresos esperados, puntos observados,
  vertical punteada en el óptimo), tabla precio/ventas/ingresos, tabla de parámetros posteriores,
  estados de carga y error, sin dependencias externas.
- [x] **T8** Servir la UI: `GET /` devuelve el HTML, `mount("/static")`, se elimina el PNG en base64
  y `matplotlib` de las dependencias.
- [x] **T9** Tests de assets (HTML servido, assets 200, referencias cruzadas), `node --check` sobre
  el JS y corrida real end-to-end contra PyMC de verdad.

**Superficies de escritura WU2:** `price_optimizer/**`, `tests/**`, `pyproject.toml`.

**DoD WU2:** ✅ suite verde (41 tests), `node --check` limpio, corrida real de `POST /optimise` con PyMC
instalado devolviendo un óptimo dentro del grid (23.33 con el request de 5 observaciones).

### WU3 · Limpieza y documentación ✅

- [x] **T10** Borrar `flutter_app/`.
- [x] **T11** Reescribir `README.md` (quickstart con `uv`, contrato de la API, decisiones, riesgos
  actualizados, corrección del 400→422 y de las rutas stale `2/Financieras/`) y actualizar
  `RECOMENDACIONES.md` (se cae la sección Flutter, se marcan los ítems hechos, se re-prioriza).
  Limpiar la sección Flutter muerta del `.gitignore` raíz.
- [x] **T12** Verificación independiente (`gentle-ai-verify`) sobre el entregable completo. Veredicto
  inicial: **fail** con 6 hallazgos; todos triados y resueltos (ver abajo). Review nativo RDD: **aprobado
  y reconocido** (ver «Cierre»).

**Superficies de escritura WU3:** `README.md`, `RECOMENDACIONES.md`, `.gitignore`. Puede borrar:
`flutter_app/`.

### Correcciones posteriores al review del parent

- [x] **T13** `cli.py` abría el navegador 0.5 s después de arrancar, pero `import pymc` tarda ~7.6 s:
  el usuario veía un error de conexión. Ahora espera a `uvicorn.Server.started`, con test de
  regresión en `tests/test_cli.py`.

## Verificación

| Qué | Cómo | Quién |
|-----|------|-------|
| Modelo y validaciones | `uv run pytest -q` | writer + verificación independiente |
| Capa HTTP | `uv run pytest -q tests/test_api.py -v` | writer + verificación independiente |
| Sampler real | `uv run pytest -q -m integration` | verificación de WU2 |
| Estilo Python | `uv run ruff check .` | writer |
| Sintaxis JS | `node --check price_optimizer/static/app.js` | verificación de WU2 |
| Corrida real | `uv run price-opt` + `curl POST /optimise` | verificación de WU2 |
| Entregable completo | revisión nativa RDD al cerrar | parent, con consentimiento del humano |

## Riesgos y límites

- **Carga de revisión alta:** el diff total estimado es de ~1000 líneas agregadas (de las cuales
  ~535 son borrado de `flutter_app/`). Se entrega por unidades de trabajo para que la revisión sea
  legible; si el usuario quiere PRs, conviene encadenar una por WU.
- **Resolución de dependencias:** `pymc>=5.16,<6` con Python 3.11 debería resolver con numpy 2.x;
  si falla, está el fallback pineado de T1.
- **Riesgo de falso verde que se elimina:** al no haber más módulo PyMC falso en `conftest.py`, un
  test marcado `integration` que pase implica que el sampler real corrió.
- **Sin verificación visual del navegador:** la verificación de la UI es estructural (HTML/JS
  servidos, sintaxis, contrato del JSON) más una corrida real del endpoint. No hay captura de
  pantalla automatizada.

## Hallazgos de la verificación independiente (y su resolución)

La verificación independiente devolvió **fail** con seis hallazgos. Ninguno bloqueó la entrega, pero
todos se resolvieron antes del review nativo:

| # | Severidad | Hallazgo | Resolución |
|---|-----------|----------|------------|
| H1 | Alta | El README documentaba el grid como "finitos y positivos" y el cliente rechazaba `<= 0`, pero la API aceptaba precios nulos o negativos | Se validó positividad estricta en `price_optimizer/api.py` (422 con mensaje en español) y se agregó test; evidencia: `price_grid: [0, ...]` -> 422 `"Los precios del grid deben ser mayores que cero."` |
| H2 | Media | El README afirmaba que los mensajes 422 venían en español, pero los límites de rango los genera Pydantic en inglés | Se corrigió §2.4 describiendo ambas fuentes de mensaje |
| H3 | Media | El ejemplo de `curl` usaba precios 10-30 y su respuesta mostraba un grid de 10-35: no coincidían | Se corrió el request documentado y se pegó esa salida real (paso 0.202, óptimo 23.33), aclarando la estocasticidad |
| H4 | Baja | El conteo de tests (34) quedó desactualizado al agregar tests | Corregido a 41 en README y RECOMENDACIONES; se agregó `tests/test_cli.py` a la tabla |
| H5 | Media | Sin cobertura de NaN/infinito, grid no positivo, y ninguna prueba de que los parámetros del request lleguen al modelo | Agregados 3 tests, incluido uno de reenvío de parámetros que captura los argumentos del modelo |
| H6 | Media | El timeout devuelve 504 pero no cancela el hilo que muestrea, y no estaba documentado entre los riesgos | Se agregó a la sección de riesgos conocidos |

También se corrigieron dos defectos detectados en el review del parent, antes de la verificación:

- El test de "sin URLs externas" era burlable: el JS ofuscaba el namespace SVG para satisfacerlo
  (`["http", "//www.w3.org/2000/svg"].join(":")`). Se restauró el literal y el test ahora verifica la
  propiedad real (que `src`/`href` sean same-origin y que no haya `fetch` a un host externo).
- El CLI abría el navegador antes de que el servidor existiera (T13).

## Cierre

- **Entorno verificado**: `uv run pytest -q` = 41 passed + 1 integration deseleccionado;
  `uv run pytest -q -m integration` = sampler real OK; `uv run ruff check .` limpio;
  `node --check price_optimizer/static/app.js` OK.
- **Corrida real end-to-end**: `uv run price-opt` sirve la UI, `/docs` responde 200 y
  `POST /optimise` con el payload de 5 observaciones devuelve óptimo 23.33 en 18.3 s.
- **Review nativo RDD**: linaje `review-11e8f9041397401b`, tier medium, lente consolidada
  `review-reliability`, 33 archivos y 4340 líneas cambiadas. Resultado: **approved**, authority
  quemada con `gentle-ai.review-acknowledged/v1`. Sin hallazgos bloqueantes; una advertencia
  informativa, `R3-ui-submit-coverage-gap` (`tests/test_static_ui.py:25-33`): la cobertura de la UI es
  estructural y no ejercita el camino de submit del formulario. Queda como trabajo posterior, no
  reabre el review.
- **Pendiente de decisión del usuario**: commits (hoy hay borrados staged y el resto sin stagear),
  captura o GIF para el README, y si `odd/` debe formar parte del portafolio público.

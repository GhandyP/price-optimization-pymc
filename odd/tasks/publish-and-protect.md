# ODD · Publicar y proteger: commits, CI y captura

**Estado:** ✅ cerrada · **Fecha:** 2026-09-17 · **Rama:** `main` · **Commits:** `90da488`, `3361145`, `9aa2a3d` y el commit `docs:` de la captura.

## Objetivo

Convertir el trabajo ya hecho (feature `web-ui-replacement`, revisada y aprobada) en un repositorio
**publicable**: historia de commits legible, CI que corra en cada push, y una captura real de la
interfaz en el README.

Punto de partida real: un solo commit (`07e6882`, la versión con Flutter), 23 cambios sin commitear y
ningún CI. En GitHub, el proyecto todavía es el viejo.

## Ajuste al esquema aprobado (y por qué)

El esquema de 3 commits por capa que aprobaste no deja commits **bisecables**:

- con el paquete migrado pero sin `price_optimizer/static/`, la API no puede servir `/`;
- con `flutter_app/` todavía en el árbol, el repo queda con dos frontends y no se sabe cuál corre.

Se reemplaza por una división que deja **cada commit funcional y con su documentación al día**:

| Commit | Contenido |
|--------|-----------|
| C1 | `feat!:` Migración completa: paquete `price_optimizer/`, UI web, tests, borrados, README y RECOMENDACIONES reescritos |
| C2 | `ci:` Workflow de GitHub Actions para cada push y PR |
| C3 | `fix:` Ejes del gráfico legibles, marcas redondas y favicon (defectos que aparecieron al mirar la captura real) |
| C4 | `docs:` Captura real en `docs/screenshot.png` y la documentación que la acompaña |

El esquema aprobado hablaba de tres commits; fueron cuatro. La captura real de la interfaz mostró dos
defectos del gráfico (el eje X sin etiquetas de precios y las marcas del eje Y con números arbitrarios)
y un 404 de favicon en cada carga de página. Eso es un arreglo de código, no documentación, así que va
en su propio commit y la captura pasa al siguiente.

C1 es grande por naturaleza: **es una migración de stack**. Partirla por capas produce commits que no
funcionan; la regla de cambios chicos aplica a features nuevas, no a un reemplazo de frontend. El
review nativo se hace sobre el **delta** (C1..HEAD): el código de C1 ya está cubierto por el review
aprobado del linaje `review-11e8f9041397401b`.

## Decisiones cerradas

| # | Decisión | Motivo |
|---|----------|--------|
| P1 | Tres commits: migración / CI / captura | Cada uno bisecable y con docs al día, sin estados intermedios rotos |
| P2 | `actions/checkout@v7` y `astral-sh/setup-uv@v10.0.1` | `v7` es la major vigente de checkout (2026-06): es un tag móvil a propósito, de primera parte, que recibe parches de seguridad. `setup-uv@v10.0.1` es de terceros y está fijado a un tag inmutable (la release declara `immutable: true`, verificado contra la API de GitHub) |
| P3 | Matriz de Python 3.11 y 3.12 con guard de versión | `requires-python = ">=3.11,<3.13"` deja de ser aspiracional; el guard hace que la matriz no pueda pasar probando dos veces lo mismo |
| P4 | `uv sync --locked` en CI | El lock es el contrato: si `uv.lock` no coincide con `pyproject.toml`, CI falla en vez de resolver otra cosa |
| P5 | Captura real con `firefox --headless --screenshot` sobre el servidor levantado | Firefox está instalado en la máquina: captura de verdad, no mockup ni placeholder |
| P6 | **No se hace push**: lo decide el usuario | Publicar es una decisión humana, no un paso automático del plan |

## Tareas

- [x] **T1** Marcar el plan de `web-ui-replacement` como **cerrada**, con fecha y resultado del review.
- [x] **T2** **C1** `feat!:` migración completa — `pyproject.toml`, `.python-version`, `uv.lock`,
  `price_optimizer/**`, `tests/**`, `.gitignore`, `README.md`, `RECOMENDACIONES.md`,
  `odd/tasks/web-ui-replacement.md`, y los borrados `backend/**`, `flutter_app/**`,
  `Optimizacion_Precios_PyMC.py`, `pytest.ini`. Footer `BREAKING CHANGE`: `GET /` ya no devuelve JSON
  y la respuesta de `/optimise` no incluye `revenue_plot_base64`.
- [x] **T3** `.github/workflows/ci.yml`: matriz 3.11/3.12, `uv sync --locked`, guard de versión de
  Python, `ruff`, `pytest -q`, `pytest -q -m integration` (sampler real) y `node --check`.
- [x] **T4** **C2** `ci:` workflow + este plan.
- [x] **T5** Captura real de la interfaz con Chromium headless y Playwright sobre el servidor levantado (inferencia real, `draws=500`, `tune=200`), guardada como `docs/screenshot.png`.
- [x] **T6** **C4** `docs:` captura y sección «Cómo se ve» en el README.
- [x] **T7** Verificación independiente (`gentle-ai-verify`): validez del YAML, referencias de acción,
  espejo entre los comandos del workflow y los documentados, y las afirmaciones del README.
- [ ] **T8** Review nativo RDD del delta `C1..HEAD`.
- [ ] **T9** Reporte final y **decisión de push** (turno del usuario).

**Superficies de escritura:** `.github/workflows/ci.yml`, `docs/**`, `README.md`,
`RECOMENDACIONES.md`, `odd/**`.

## Hallazgos de la captura real

Mirar la interfaz en un navegador de verdad —y no solo verificar que los archivos se sirven— encontró
tres defectos que ninguna prueba veía:

| # | Defecto | Evidencia | Resolución |
|---|---------|-----------|------------|
| V1 | El eje X no tenía etiquetas de precios: solo la línea del eje y la palabra «Precio», así que la escala era ilegible | Captura de 1280×1206 del estado con resultados | Cinco marcas (mínimo, tres intermedios, máximo) formateadas con `format(price, 2)` |
| V2 | Las marcas del eje Y eran números arbitrarios: 1.422 / 1.138 / 853 / 569 / 284, porque salían de dividir el pico crudo por cinco | Misma captura | La escala se ajusta a un paso «redondo» (factores 1 · 1,5 · 2 · 2,5 · 3 · 4 · 5 · 6 · 8 · 10): para un pico de 1.422,57 las marcas quedan 0 / 300 / 600 / 900 / 1200 / 1500 y la curva sigue llenando el gráfico |
| V3 | Cada carga de página pedía `/favicon.ico` y el servidor respondía 404 (visible en la consola del navegador y en el log) | Consola del navegador y `log_requests` | Se agrega `price_optimizer/static/favicon.svg`, se referencia desde el `<head>` y el test de assets lo verifica |

La captura se tomó con Chromium headless (Playwright) contra el servidor real: la página se envió, se
esperó el resultado de la inferencia real y recién ahí se capturó. Verificación de que la UI funciona de
punta a punta, no solo de que los archivos existen.

## Verificación

| Qué | Cómo | Quién |
|-----|------|-------|
| Comandos del CI | Los mismos seis comandos, corridos localmente antes de commitear | parent |
| Mecanismo de la matriz | `uv sync --python 3.12 --dry-run` → «Using CPython 3.12.13» (verificado: `--python` gana sobre `.python-version`) | parent |
| Workflow | YAML parse + referencias de acción contra la fuente oficial + espejo de comandos | verificación independiente |
| Captura | El PNG existe, tiene tamaño razonable y muestra la UI real servida por la app | parent |
| Defectos visuales | Captura real del navegador, mirada y corregida (V1-V3) | parent |
| Delta completo | Review nativo RDD | parent, con consentimiento del humano |

## Riesgos y límites

- **El workflow no se puede ejecutar localmente.** Se valida por estructura y por espejo exacto con los
  comandos verificados en la máquina; la prueba definitiva es el primer push, que es decisión tuya.
- **La matriz duplica el tiempo de CI** (dos jobs, cada uno baja PyMC). El límite gratuito de Actions
  para repos públicos lo absorbe sin problema.
- **La captura es de 1280×1206 px de CSS (2560×2412 a 2×) y del navegador headless**: es una captura real de la app, no un diseño idealizado. Si el layout no se ve bien a ese ancho, la captura lo va a mostrar (y conviene arreglar el layout, no la captura).
- **El delta del review es chico pero incluye un archivo ejecutable** (`.github/`), así que no califica
  como «edición pasiva de documentación» y corresponde el preflight.

## Resultado de la verificación independiente

Veredicto: **pass-with-findings**. Reprodujo el espejo del CI y confirmó los números de la
documentación (41 + 1 tests, 2 warnings de `starlette.testclient` y `anyio`, la aritmética de la
captura — 121,0406 − 2,7016 × 22,37 ≈ 60,6 ventas y 1.355,75 de ingreso), y verificó contra la API de
GitHub que `setup-uv@v10.0.1` es una release inmutable.

| # | Sev. | Hallazgo | Resolución |
|---|------|----------|------------|
| F1 | Media | `actions/checkout@v7` es un tag móvil, no una release inmutable, y la doc no distinguía los dos criterios de fijado | Se precisa la política en P2 y en el README: primera parte → major vigente; terceros → tag inmutable |
| F2 | Baja | El plan decía que la captura tenía un tamaño incorrecto y en realidad es de 1280×1206 CSS (2560×2412 a 2×) | Corregido |
| F3 | Baja | Con ingresos chicos (pico 3) las marcas del eje Y se redondeaban y se duplicaban: `4 / 3 / 2 / 2 / 1 / 0` | Los decimales ahora se derivan del paso de la escala |
| F4 | Info | El CI corre seis comandos y el README documentaba cuatro | Se aclara que el CI corre esos cuatro más el sync y el guard |

## Cierre

- **Commits**: `90da488` migración, `3361145` CI, `9aa2a3d` gráfico y favicon, más el commit `docs:` con
  la captura y esta actualización del plan.
- **Espejo local del CI, verificado antes de commitear**: `uv sync --locked` sin cambios pendientes,
  guard de versión de Python OK, `uv run ruff check .` limpio, `uv run pytest -q` = 41 pasados + 1
  deseleccionado, `uv run pytest -q -m integration` = 1 pasado con el sampler real, y
  `node --check price_optimizer/static/app.js` OK.
- **Captura**: `docs/screenshot.png`, 1280×1206 (2×), con inferencia real y precio óptimo 22,37.
- **Pendiente**: la verificación independiente del workflow y el review nativo del delta (T7 y T8), y la
  decisión de push del usuario (T9). El push **no** se ejecuta sin pedido explícito.

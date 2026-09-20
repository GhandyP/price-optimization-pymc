# ODD · Publicar y proteger: commits, CI y captura

**Estado:** en curso · **Fecha:** 2026-09-17 · **Rama:** `main`

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
| C1 | Migración completa: paquete `price_optimizer/`, UI web, tests, borrados, README y RECOMENDACIONES reescritos |
| C2 | CI: `.github/workflows/ci.yml` + el plan de esta feature |
| C3 | Captura real de la interfaz + sección «Cómo se ve» en el README |

C1 es grande por naturaleza: **es una migración de stack**. Partirla por capas produce commits que no
funcionan; la regla de cambios chicos aplica a features nuevas, no a un reemplazo de frontend. El
review nativo se hace sobre el **delta** (C1..HEAD): el código de C1 ya está cubierto por el review
aprobado del linaje `review-11e8f9041397401b`.

## Decisiones cerradas

| # | Decisión | Motivo |
|---|----------|--------|
| P1 | Tres commits: migración / CI / captura | Cada uno bisecable y con docs al día, sin estados intermedios rotos |
| P2 | `actions/checkout@v7` y `astral-sh/setup-uv@v10.0.1` | `v7` es la major vigente de checkout (2026-06); `v10.0.1` de setup-uv usa *immutable releases*. Verificado contra la fuente oficial, no de memoria |
| P3 | Matriz de Python 3.11 y 3.12 con guard de versión | `requires-python = ">=3.11,<3.13"` deja de ser aspiracional; el guard hace que la matriz no pueda pasar probando dos veces lo mismo |
| P4 | `uv sync --locked` en CI | El lock es el contrato: si `uv.lock` no coincide con `pyproject.toml`, CI falla en vez de resolver otra cosa |
| P5 | Captura real con `firefox --headless --screenshot` sobre el servidor levantado | Firefox está instalado en la máquina: captura de verdad, no mockup ni placeholder |
| P6 | **No se hace push**: lo decide el usuario | Publicar es una decisión humana, no un paso automático del plan |

## Tareas

- [ ] **T1** Marcar el plan de `web-ui-replacement` como **cerrada**, con fecha y resultado del review.
- [ ] **T2** **C1** `feat!:` migración completa — `pyproject.toml`, `.python-version`, `uv.lock`,
  `price_optimizer/**`, `tests/**`, `.gitignore`, `README.md`, `RECOMENDACIONES.md`,
  `odd/tasks/web-ui-replacement.md`, y los borrados `backend/**`, `flutter_app/**`,
  `Optimizacion_Precios_PyMC.py`, `pytest.ini`. Footer `BREAKING CHANGE`: `GET /` ya no devuelve JSON
  y la respuesta de `/optimise` no incluye `revenue_plot_base64`.
- [ ] **T3** `.github/workflows/ci.yml`: matriz 3.11/3.12, `uv sync --locked`, guard de versión de
  Python, `ruff`, `pytest -q`, `pytest -q -m integration` (sampler real) y `node --check`.
- [ ] **T4** **C2** `ci:` workflow + este plan.
- [ ] **T5** Captura real de la interfaz (firefox headless contra `price-opt`) guardada como
  `docs/screenshot.png`, y sección «Cómo se ve» en el README.
- [ ] **T6** **C3** `docs:` captura y sección nueva.
- [ ] **T7** Verificación independiente (`gentle-ai-verify`): validez del YAML, referencias de acción,
  espejo entre los comandos del workflow y los documentados, y las afirmaciones del README.
- [ ] **T8** Review nativo RDD del delta `C1..HEAD`.
- [ ] **T9** Reporte final y **decisión de push** (turno del usuario).

**Superficies de escritura:** `.github/workflows/ci.yml`, `docs/**`, `README.md`,
`RECOMENDACIONES.md`, `odd/**`.

## Verificación

| Qué | Cómo | Quién |
|-----|------|-------|
| Comandos del CI | Los mismos seis comandos, corridos localmente antes de commitear | parent |
| Mecanismo de la matriz | `uv sync --python 3.12 --dry-run` → «Using CPython 3.12.13» (verificado: `--python` gana sobre `.python-version`) | parent |
| Workflow | YAML parse + referencias de acción contra la fuente oficial + espejo de comandos | verificación independiente |
| Captura | El PNG existe, tiene tamaño razonable y muestra la UI real servida por la app | parent |
| Delta completo | Review nativo RDD | parent, con consentimiento del humano |

## Riesgos y límites

- **El workflow no se puede ejecutar localmente.** Se valida por estructura y por espejo exacto con los
  comandos verificados en la máquina; la prueba definitiva es el primer push, que es decisión tuya.
- **La matriz duplica el tiempo de CI** (dos jobs, cada uno baja PyMC). El límite gratuito de Actions
  para repos públicos lo absorbe sin problema.
- **La captura es de 1280×900 y del navegador headless**: es una captura real de la app, no un diseño
  idealizado. Si el layout no se ve bien a ese ancho, la captura lo va a mostrar (y conviene arreglar
  el layout, no la captura).
- **El delta del review es chico pero incluye un archivo ejecutable** (`.github/`), así que no califica
  como «edición pasiva de documentación» y corresponde el preflight.

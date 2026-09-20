# ODD · Credibilidad del modelo

**Estado:** en curso · **Fecha:** 2026-09-20 · **Rama:** `feat/model-credibility` (commits por unidad de trabajo)

## Objetivo

Que el número que el proyecto muestra sea **defendible**: que la elasticidad la digan los datos y no
el prior, que la incertidumbre sea visible, y que el sistema avise cuando el resultado no es confiable
en vez de devolver un punto sin contexto.

## Contexto: qué está mal hoy (verificado, no supuesto)

| Problema | Evidencia |
|----------|-----------|
| El prior empuja la elasticidad | `pendiente ~ Normal(mu=-1, sigma=1)` en `model.py:68` mientras la posterior da −2,69 con los datos de ejemplo: más de 1,5 desvíos del prior |
| El intercepto se interpreta en un punto absurdo | `intercepto ~ Normal(mu=max(ventas), sigma=max(desvío, 10))` en `model.py:65`: modela las ventas a **precio 0**, fuera del rango analizado |
| El óptimo puede caer en el borde y no se avisa | `np.argmax` en `model.py:92`, sin chequeo de extremos; el grid automático solo cubre el rango observado |
| Las ventas esperadas pueden ser negativas | En el modelo polinómico no hay recorte antes de calcular ingresos |
| La incertidumbre no viaja | La respuesta solo lleva medias posteriores; el valor del enfoque bayesiano queda afuera |
| La convergencia no viaja | La corrida real del PR anterior logueó 7 divergencias y avisos de R-hat **solo en el log del servidor** |

## Decisiones cerradas

| # | Decisión | Motivo |
|---|----------|--------|
| M1 | Priors débilmente informativos en la escala de los datos, con el **precio centrado en su media** | El intercepto pasa a ser "ventas al precio promedio", interpretable; el prior del slope deja de empujar hacia −1 |
| M2 | Escalas con piso: si el desvío es 0, la escala cae a un valor positivo derivado del nivel | Evita `sigma=0` en priors con datos degenerados (todas las ventas iguales) |
| M3 | HDI 90% por punto del grid con `az.hdi(hdi_prob=0.9)` | Forma verificada: `(n_grid, 2)`. Es la API vigente de arviz 0.23.4, sin reinventar cuantiles |
| M4 | Diagnósticos R-hat y ESS en la respuesta, con umbrales explícitos: convergencia = `max_rhat <= 1.01` y `min_ess >= 100` | Convierte un aviso que hoy queda en el log en información del cliente |
| M5 | **`NaN` nunca sale en el JSON**: los diagnósticos que no se pueden calcular van como `null` | `NaN` no es JSON válido: `JSON.parse` del navegador falla. Con 1 cadena `az.rhat` devuelve `nan` |
| M6 | Avisos (`warnings`) como lista de strings en español, no como excepción | Un óptimo de borde o un R-hat alto no son errores: son resultados que exigen contexto |
| M7 | Recorte de `expected_sales` a 0 **antes** de calcular ingresos, con aviso cuando recorta | Una demanda negativa no tiene sentido de negocio; el recorte se informa, no se esconde |
| M8 | `arviz` pasa al grupo de dependencias de **runtime** y se regenera `uv.lock` | `model.py` lo va a importar; el CI usa `uv sync --locked`, así que sin re-lockear falla |
| M9 | El contrato del **request** no cambia; la respuesta solo **agrega** campos | Es aditivo: la UI vieja seguiría funcionando. Cambia el *significado* del intercepto, y eso se documenta |

## Unidades de trabajo

### WU1 · Modelo

- [x] **T1** `_data_scale()` (desvío con piso) y priors calibrados:
  `intercepto ~ Normal(mu=mean(ventas), sigma=2·escala_ventas)`,
  `pendiente ~ Normal(mu=0, sigma=3·escala_ventas/escala_precio)`,
  `beta_k ~ Normal(mu=0, sigma=3·escala_ventas/escala_precio^k)`,
  `sigma_ventas ~ HalfNormal(sigma=escala_ventas)`. Precio centrado en su media dentro del modelo.
- [x] **T2** HDI 90% de ventas e ingresos por punto del grid, desde las muestras por draw.
- [x] **T3** Diagnósticos: `rhat` y `ess` por parámetro, `max_rhat`, `min_ess`, `converged`, con
  umbrales como constantes de módulo y `NaN → None`.
- [x] **T4** Avisos: óptimo en el borde del grid; recorte de ventas a cero (con la cantidad de puntos);
  no convergencia (R-hat alto, ESS bajo); R-hat no calculable por falta de cadenas.
- [x] **T5** `arviz` a dependencias de runtime + `uv lock`.
- [x] **T6** Tests: fixtures a **2 cadenas** (con 1, `az.rhat` da `nan` y el caso no se prueba),
  recorte y su aviso, óptimo de borde, HDI con largo y monotonía (`low <= media <= high`),
  `converged` falso con una traza mal mezclada, y `_data_scale` con datos degenerados.

### WU2 · API

- [x] **T7** Campos nuevos en la respuesta: `expected_sales_hdi_low/_high`,
  `expected_revenue_hdi_low/_high`, `diagnostics` (`rhat`, `ess`, `max_rhat`, `min_ess`, `converged`),
  `warnings`. `NaN → null` en el serializado. Tests del contrato nuevo y de que el request no cambió.

### WU3 · UI y documentación

- [x] **T8** UI: banda de incertidumbre (HDI 90%) detrás de la línea de ingresos, columnas de rango en
  la tabla, avisos visibles (ámbar, no rojo) y etiquetas legibles para los parámetros
  (`intercepto` → "Ventas al precio promedio", `pendiente` → "Elasticidad (pendiente)", etcétera).
- [x] **T9** README y RECOMENDACIONES: reescribir «Límites que conocemos» (los priors ya no sesgan;
  los nuevos límites son los umbrales de convergencia, la definición de HDI y el recorte), marcar
  hechos los ítems 1.1 a 1.5 y **regenerar la captura**, porque el gráfico y los números cambian.
- [ ] **T10** Verificación independiente (`gentle-ai-verify`).
- [ ] **T11** Review nativo del delta y reporte final.

**Superficies de escritura:** `price_optimizer/model.py`, `price_optimizer/api.py`,
`price_optimizer/static/**`, `tests/**`, `pyproject.toml`, `uv.lock`, `README.md`,
`RECOMENDACIONES.md`, `docs/screenshot.png`, `odd/**`.

## Defectos encontrados durante la revisión

- `az.hdi` recibía un array 2-D ambiguo; ahora la llamada nombra explícitamente sus dimensiones para evitar la reinterpretación anunciada por ArviZ.
- PyMC recomendó cuatro cadenas para diagnósticos confiables; el sampler ahora solicita cuatro cadenas.

## Verificación

| Qué | Cómo |
|-----|------|
| Priors ya no sesgan | Comparar la posterior del slope contra la pendiente de mínimos cuadrados de los mismos datos: deben quedar cerca |
| HDI | Largo igual al grid y `low <= media <= high` en todos los puntos |
| Diagnósticos | `converged` verdadero en una corrida real con `draws=2000, tune=1000`; falso con una traza mal mezclada |
| JSON válido | La respuesta no contiene `NaN` (verificable con `json.loads` y con el `JSON.parse` del navegador) |
| Recorte y borde | Tests específicos, más una corrida real buscando ambos casos |
| Suite completa | `uv run pytest -q` + `uv run pytest -q -m integration` + `ruff` + `node --check` |
| Entregable | Verificación independiente y review nativo, como en la feature anterior |

## Riesgos y límites

- **Los números cambian a propósito.** El README, la captura y cualquier cifra citada se actualizan en
  la misma feature; si no, la documentación miente.
- **Cambio de significado, no de contrato.** `parameter_means["intercepto"]` pasa de "ventas a precio 0"
  a "ventas al precio promedio". Las claves siguen igual, así que un consumidor viejo no se rompe pero
  puede malinterpretar el número: por eso se documenta y la UI lo etiqueta.
- **Umbrales de convergencia elegidos, no revelados.** `max_rhat <= 1.01` y `min_ess >= 100` son
  convenciones; quedan como constantes visibles y documentadas.
- **Carga de revisión.** Tres unidades y una captura nueva: conviene revisar por tramos, con el mismo
  criterio aprendido en la feature anterior (base-ref al recibo anterior, no al origen).

# Recomendaciones pendientes

> Documento vivo con las mejoras recomendadas para `price-optimization-pymc`.
> Incluye mejoras implementadas y pendientes — priorizadas para futuras iteraciones.

## Hecho recientemente

- **Migración de Flutter a una UI web servida por FastAPI** (antes: app Flutter + API con matplotlib y
  PNG en base64). El proyecto ahora corre con `uv run price-opt` y se prueba con `uv run pytest`.
  Detalle y decisiones: `odd/tasks/web-ui-replacement.md`.
- **Tests de la capa HTTP**: `/optimise`, validaciones, 400 y 504 estaban sin cobertura.
- **Entorno reproducible**: `uv` + `.python-version` + `uv.lock` versionado.
- **Publicación**: commits por unidad de trabajo, CI en GitHub Actions (matriz de Python 3.11 y 3.12) y
  una captura real de la interfaz en el README (`docs/screenshot.png`).
- **Credibilidad del modelo**: priors calibrados, guard de óptimo en el borde, recorte de ventas negativas,
  intervalos HDI 90% y diagnósticos de convergencia visibles en la API y la UI.

---

## 1. Modelo (prioridad alta)

### 1.1 Priors calibrados — ✅ Hecho
Antes de este cambio, el prior de la pendiente estaba centrado en -1 con sigma 1 y la posterior quedaba
en `-2.69`, a más de 1.5 desvíos del prior. Con 3 a 30 observaciones, ese prior podía dominar y
**sesgar la elasticidad hacia valores débiles**, moviendo a su vez el precio óptimo. Se implementaron
priors débilmente informativos escalados con `_data_scale`, el precio se centró en su media y
`intercepto` pasó a significar las ventas esperadas al precio observado promedio. En el ejemplo de
diez filas de la app, la pendiente posterior ahora es `-2.7614`, frente a `-2.7613` por mínimos
cuadrados ordinarios; en un dataset de tres puntos, la diferencia es aproximadamente `+0.19` porque
hay poca información.

### 1.2 Guard de extrapolación en el óptimo — ✅ Hecho
Antes de este cambio, el grid automático cubría solo el rango observado. Si el máximo real de ingresos
quedaba fuera de ese rango, el `argmax` caía en el borde y el resultado se reportaba como si fuera un
óptimo interior. Ahora se devuelve una advertencia explícita cuando `optimal_price` es el primero o
el último punto del grid, para que un óptimo de borde no pase inadvertido.

### 1.3 Recorte de ventas esperadas negativas — ✅ Hecho
Antes de este cambio, con el modelo polinómico `expected_sales` podía volverse negativa a precios
altos y los ingresos "esperados" seguían esa negatividad. Ahora las ventas esperadas se recortan en 0
antes de calcular los ingresos.

### 1.4 Intervalos de credibilidad (HDI 90%) — ✅ Hecho
Antes de este cambio, el modelo devolvía medias posteriores sin cuantificar la incertidumbre. Ahora
devuelve intervalos HDI del 90% para `expected_sales` y `expected_revenue`, que permiten dibujar
bandas de incertidumbre en el gráfico además de la línea y el punto.

### 1.5 Diagnósticos de convergencia en la respuesta — ✅ Hecho
Antes de este cambio, PyMC escribía `rhat statistic is larger than 1.01` en el log del servidor y
nadie se enteraba. Ahora la respuesta expone R-hat y ESS por parámetro y muestra una advertencia
visible en la UI cuando el muestreo no convergió, para evitar decisiones de precios con cadenas mal
mezcladas.

### 1.6 Modelo log-log (`model_type="loglog"`)
Alternativa simple al polinomio: `log(ventas) ~ log(precio)`. El coeficiente es **directamente** la
elasticidad, lo que simplifica la lectura de negocio y evita estimar elasticidad variable con
polinomios que oscilan en los extremos.

### 1.7 Splines bayesianos
El polinomio global de grado 2-3 captura curvatura simple pero puede oscilar en los bordes. Un modelo
de splines (B-splines con priors sobre los coeficientes, o `pm.gp`) modela elasticidad variable de
forma más controlada.

---

## 2. Infraestructura de despliegue

- **Dockerfile de producción**: imagen `python:3.12-slim` con `uv sync --no-dev` y
  `uv run price-opt --host 0.0.0.0`. Sin capa de frontend: la UI viene en el paquete.
- **docker-compose.yml para desarrollo local**: levantar todo con un comando, sin depender de que quien
  clona tenga Python 3.11.

## 3. Backend

- **Cola de trabajos para la inferencia**: `/optimise` muestrea en un thread con timeout de 120 s. Bajo
  concurrencia, PyMC satura el CPU y las requests se apilan. Opciones: workers con cola (Redis + RQ /
  Celery) o rate limiting. Para el caso de uso actual (demo local) no es urgente, pero es el primer
  cuello de botella real.
- **Límite de tasa y tamaño de payload**: hoy cualquier cliente puede pedir `draws=10000` sin límite de
  frecuencia.
- **Formato de error consistente**: `detail` es string en 400/504 y lista de objetos en 422. Un formato
  único `{"error": ..., "detail": ...}` simplificaría a los consumidores. La UI ya maneja ambos.
- **Ejemplos en los schemas de Pydantic** (`examples=`): mejora la experiencia de `/docs`.

## 4. UI web

- **Tests unitarios del JavaScript**: la validación y el parseo de `app.js` son lógica pura y hoy solo
  se verifican de forma estructural. `node --test` es built-in (no agrega dependencias), pero requiere
  decidir cómo se exponen las funciones (ESM o un shim de exports) sin romper el "sin build step".
  Esto incluye el hallazgo informativo `R3-ui-submit-coverage-gap` del review nativo: el camino de
  submit del formulario (parseo → validación → fetch → render) no está cubierto por ningún test.
- **Exportar resultados (CSV/JSON)**: un botón para bajar la tabla precio / ventas / ingresos.
- **Scatter antes de optimizar**: mostrar las observaciones apenas se cargan permite detectar datos
  anómalos o relaciones no lineales a simple vista, antes de gastar 20 segundos de inferencia.
- **Banda de incertidumbre en el gráfico**: depende de 1.4.
- **`Content-Security-Policy`**: hoy no hay CSP explícita (el HTML se arma con datos de la propia API).
- **Accesibilidad**: revisar contraste, foco visible y semántica de los campos; ya hay `label for`,
  `aria-live` y `role/aria-labelledby` en el SVG.
- **i18n (español/inglés)**: el copy está hardcodeado en español.

## 5. Datos y producto

- **Datasets de ejemplo en el repo**: un CSV con demanda lineal, cuadrática y con ruido, generado con el
  propio modelo, para la demo y para tests con datos más realistas que 3 a 10 puntos.
- **Persistencia de resultados**: el sistema es stateless. Una SQLite con las optimizaciones hechas
  habilitaría comparaciones y seguimiento.
- **Endpoint de elasticidad puntual**: además del óptimo, devolver la elasticidad en un precio dado.

---

## Resumen priorizado

| Prioridad | Mejora | Esfuerzo | Impacto |
|-----------|--------|----------|---------|
| 1 | Cola de trabajos y rate limiting (3) | L | Medio |
| 2 | Splines bayesianos (1.7) | L | Alto |
| 3 | Dockerfile + compose (2) | M | Medio |
| 4 | Tests unitarios del JS con `node --test` (4) | M | Medio |
| 5 | Modelo log-log (1.6) | S | Medio |
| 6 | Datasets de ejemplo (5) | S | Medio |
| 7 | Modelo log-log (1.6) | S | Medio |
| 8 | Tests unitarios del JS con `node --test` (4) | M | Medio |
| 9 | Datasets de ejemplo (5) | S | Medio |
| 10 | Cola de trabajos y rate limiting (3) | L | Medio |
| 11 | Splines bayesianos (1.7) | L | Alto |

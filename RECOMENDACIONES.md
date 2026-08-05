# Recomendaciones pendientes

> Documento vivo con las mejoras recomendadas para `price-optimization-pymc`.
> No implementadas aún — priorizadas para futuras iteraciones.

---

## 1. Infraestructura y despliegue

### 1.1 Docker Compose para desarrollo local
Un `docker-compose.yml` con el backend FastAPI y (si aplica) la app web Flutter compilada permitiría levantar todo con un solo comando, sin depender de que el desarrollador tenga Python 3.10+ y Flutter instalados.

### 1.2 CI/CD con GitHub Actions
Workflow que corra `pytest` en cada push/PR y bloquee el merge si falla. Es la mejora con mejor relación impacto/esfuerzo: el repo ya tiene 16 tests que se ejecutan en ~3s. Se podría añadir un job de `flutter analyze` y `flutter test` cuando existan tests de widget.

### 1.3 Dockerfile de producción
Imagen ligera (python:3.12-slim) con solo las dependencias de runtime, sin la capa Flutter. Facilita el despliegue en cualquier plataforma (Render, Railway, Fly.io, VPS).

---

## 2. Backend

### 2.1 Cola de trabajos para la inferencia
`/optimise` ejecuta MCMC en un thread con timeout de 120s. Bajo concurrencia, PyMC satura la CPU y las requests se apilan. Opciones: workers asíncronos con cola (Redis + RQ / Celery) o rate limiting. Para el caso de uso actual (demanda interna baja) no es urgente, pero es el primer cuello de botella real en producción.

### 2.2 Intervalos de credibilidad en la respuesta
El modelo devuelve medias posteriores, pero la incertidumbre es el valor agregado del enfoque bayesiano. Añadir cuantiles (HDI al 90%) para `expected_sales` y `expected_revenue` permitiría mostrar bandas de incertidumbre en la UI, no solo un punto óptimo.

### 2.3 Diagnósticos de convergencia en la respuesta
`raw_trace` ya se expone, pero el frontend no lo usa. Mejor: exponer R-hat y ESS efectivo por parámetro (calculados con `az.summary` o equivalentes) y mostrar una advertencia si no convergió. Evita que el usuario tome decisiones con cadenas mal mezcladas.

### 2.4 Validación cruzada del grid vs observaciones
Validar que los valores de `price_grid` estén dentro de un rango razonable respecto a los precios observados (ej. no extrapolar más allá de X% del rango), para evitar predicciones sin soporte empírico.

### 2.5 Manejo estructurado de errores
Los errores ya devuelven 400/504 con detalle claro. Un formato JSON consistente `{"error": "...", "detail": "..."}` en todas las respuestas de error facilitaría el parseo en Flutter (el cliente ya intenta extraer `detail` de varias formas).

### 2.6 Endpoint de documentación de ejemplos
FastAPI ya genera `/docs` (Swagger). Añadir ejemplos explícitos a los schemas de Pydantic (`examples=`) mejoraría la experiencia de consumo de la API.

---

## 3. Modelo

### 3.1 Splines bayesianos
El polinomio global (grado 2-3) captura curvatura simple, pero puede oscilar en los extremos. Un modelo de splines (p. ej. `pm.gp` o B-splines con priors sobre los coeficientes) modela elasticidad variable de forma más flexible y controlada. Es la evolución natural del problema 1.

### 3.2 Priors con regularización
Los coeficientes polinómicos usan `sigma=1.0`. Priors tipo `pm.Horseshoe` o `sigma` con distribución (regularización bayesiana tipo lasso/ridge) reducirían el sobreajuste en datasets chicos — el repo trabaja con 3–30 observaciones.

### 3.3 Modelo log-log (elasticidad constante directa)
Alternativa simple y económica al polinomio: regresión en log(ventas) ~ log(precio). El coeficiente ES directamente la elasticidad, lo que simplifica la interpretación para el negocio. Podría ofrecerse como `model_type="loglog"`.

### 3.4 Guard contra extrapolación en el óptimo
Cuando el óptimo cae en el borde del grid (indicio de que el rango evaluado no contiene el máximo real), devolver una advertencia explícita.

---

## 4. Flutter

### 4.1 Tests de widget
No hay tests de widget actualmente. El parsing de texto (`_parsePairs`, `_parseGrid`) y la validación de formulario son lógica pura fácil de testear. `flutter test` daría red de seguridad a cambios de UI.

### 4.2 Visualización de datos observados
Mostrar un scatter de las observaciones (precio vs ventas) antes de optimizar permitiría al usuario detectar datos anómalos o relaciones no lineales a simple vista.

### 4.3 Exportar resultados (CSV/JSON)
Un botón de exportación de la tabla precio/ventas/ingresos sería útil para análisis posterior.

### 4.4 Accesibilidad
Revisar soporte de screen reader (semántica de `TextFormField` con `labelText` ya ayuda), contraste de colores y tamaño mínimo de touch targets. Material 3 ya da buena base, pero merece una auditoría manual.

### 4.5 i18n (español/inglés)
La UI está hardcodeada en español. `flutter_localizations` + ARB permitiría multiidioma, útil si el repo se muestra en un portfolio internacional.

---

## 5. Datos y producto

### 5.1 Datasets de ejemplo en el repo
Un CSV con datos sintéticos de demanda (lineal, cuadrática y con ruido) facilitaría la demo y los tests. Se puede generar con el propio modelo.

### 5.2 Persistencia de resultados
El sistema es stateless: no guarda historial de optimizaciones. Si se quiere uso continuo, una base ligera (SQLite) con las optimizaciones realizadas habilitaría comparaciones y seguimiento.

### 5.3 Endpoint de elasticidad puntual
Además del óptimo, exponer la elasticidad en el punto óptimo (o en un precio dado) da al negocio un número directamente comunicable.

---

## Resumen priorizado

| Prioridad | Mejora | Esfuerzo | Impacto |
|-----------|--------|----------|---------|
| 1 | CI GitHub Actions (pytest + flutter analyze) | S | Alto |
| 2 | Intervalos de credibilidad (HDI 90%) | M | Alto |
| 3 | Tests de widget Flutter | M | Medio |
| 4 | Docker Compose para dev local | M | Medio |
| 5 | R-hat/ESS en respuesta + alerta de no convergencia | M | Alto |
| 6 | Splines bayesianos | L | Alto |
| 7 | Endpoint elasticidad puntual | S | Medio |
| 8 | Modelo log-log (`model_type="loglog"`) | S | Medio |
| 9 | Datasets de ejemplo | S | Medio |
| 10 | Export CSV desde Flutter | M | Bajo |

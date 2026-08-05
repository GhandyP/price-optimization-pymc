# Optimizacion de Precios — PyMC + Flutter

Este módulo combina el helper PyMC `Optimizacion_Precios_PyMC.py`, una API FastAPI y una app
Flutter para estimar la **elasticidad de la demanda** mediante regresión bayesiana (lineal por
defecto, o polinómica) y encontrar el **precio que maximiza los ingresos esperados** sobre un
grid de evaluación.

El modelo asume por defecto una relación lineal entre precio y ventas. A partir de la distribución
posterior de los parámetros, se proyectan las ventas esperadas para cada precio candidato y se
identifica el punto óptimo de la curva de ingresos. Cuando la demanda es no lineal, se puede usar
el modelo polinómico (`model_type="polynomial"`, con grado configurable).

---

## 1. Backend FastAPI

### 1.1 Setup

```bash
cd 2/Financieras
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows
pip install -r backend/requirements.txt
```

### 1.2 Ejecutar

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 1.3 Endpoints

| Método | Ruta         | Descripción                                    |
|--------|--------------|------------------------------------------------|
| GET    | `/`          | Health check simple (`{"status": "ok"}`)       |
| GET    | `/health`    | Health check detallado (versión, timestamp)    |
| POST   | `/optimise`  | Ejecuta el modelo y devuelve precio óptimo     |

### 1.4 Ejemplo completo con curl

```bash
curl -X POST http://127.0.0.1:8000/optimise \
  -H "Content-Type: application/json" \
  -d '{
    "observations": [
      {"precio": 10, "ventas": 100},
      {"precio": 15, "ventas": 80},
      {"precio": 20, "ventas": 65},
      {"precio": 25, "ventas": 50},
      {"precio": 30, "ventas": 40}
    ],
    "price_grid": [10, 15, 20, 25, 30],
    "draws": 500,
    "tune": 200,
    "target_accept": 0.9
  }'
```

#### Ejemplo con demanda polinómica (variante)

```bash
curl -X POST http://127.0.0.1:8000/optimise \
  -H "Content-Type: application/json" \
  -d '{
    "observations": [
      {"precio": 10, "ventas": 100},
      {"precio": 15, "ventas": 80},
      {"precio": 20, "ventas": 65},
      {"precio": 25, "ventas": 50},
      {"precio": 30, "ventas": 40}
    ],
    "price_grid": [10, 15, 20, 25, 30],
    "model_type": "polynomial",
    "degree": 2,
    "draws": 500,
    "tune": 200
  }'
```

#### Respuesta (truncada)

```json
{
  "price_grid": [10.0, 15.0, 20.0, 25.0, 30.0],
  "expected_sales": [95.2, 78.4, 61.5, 44.7, 27.8],
  "expected_revenue": [952.0, 1176.0, 1230.0, 1117.5, 834.0],
  "optimal_price": 20.0,
  "optimal_expected_revenue": 1230.0,
  "parameter_means": {
    "intercepto": 145.3,
    "pendiente": -3.9,
    "sigma_ventas": 5.2
  },
  "revenue_plot_base64": "iVBORw0KGgo...",   ← PNG codificado en Base64
  "model_type": "linear",
  "degree": 2
}
```

### 1.5 Validaciones del request

| Campo             | Tipo        | Default    | Rango válido        |
|-------------------|-------------|------------|---------------------|
| `observations`    | `list`      | —          | ≥ 3 observaciones   |
| `price_grid`      | `list|null` | null       | ≥ 5 valores         |
| `draws`           | `int`       | 2000       | [500, 10000]        |
| `tune`            | `int`       | 1000       | [200, 10000]        |
| `target_accept`   | `float`     | 0.9        | [0.5, 0.99]         |
| `model_type`      | `str`       | `"linear"` | `"linear"` o `"polynomial"` |
| `degree`          | `int`       | 2          | [1, 5]              |

Cada observación requiere: `precio` (> 0), `ventas` (≥ 0).  
Si no se envía `price_grid`, el helper genera un grid uniforme de 100 puntos entre el mínimo y
máximo de los precios observados.  
`model_type` selecciona la forma funcional de la demanda: `"linear"` (default, elasticidad
constante) o `"polynomial"` (captura demanda no lineal mediante un polinomio de grado `degree`).
Con `model_type="polynomial"`, `degree` debe ser estrictamente menor al número de observaciones
enviadas para evitar sobreajuste.

---

## 2. App Flutter

### 2.1 Setup

```bash
cd 2/Financieras/flutter_app
flutter pub get
cp .env.example .env      # si existe; o crear manualmente
```

### 2.2 Configurar baseUrl

La app usa `flutter_dotenv` para leer `API_BASE_URL` desde el archivo `.env`:

```env
API_BASE_URL=http://127.0.0.1:8000
```

| Entorno                  | Valor `.env`                     |
|--------------------------|----------------------------------|
| Desktop / navegador web  | `http://127.0.0.1:8000`          |
| Emulador Android         | `http://10.0.2.2:8000`           |
| Emulador iOS             | `http://127.0.0.1:8000`          |
| Dispositivo físico       | `http://<IP-local>:8000`         |

Si no se encuentra el archivo `.env`, usa `http://127.0.0.1:8000` como fallback.

### 2.3 Ejecutar

```bash
flutter run
```

### 2.4 Interfaz de usuario

- **Editor de datos**: entrada multilínea con pares `precio, ventas` (una observación por línea).
- **Grid personalizado** (opcional): lista separada por comas de precios a evaluar (mín. 5).
- **Selector de modelo**: dropdown con "Lineal" (`linear`, default) o "Polinómico" (`polynomial`).
  Al elegir "Polinómico" se habilita el campo **Grado del polinomio** (1–5, default 2).
- **Hiperparámetros**: `draws` (500–10000), `tune` (200–10000), `target_accept` (0.5–0.99).
- **Resultados**: tarjeta resumen con precio óptimo e ingreso esperado, tabla de precio/ventas/ingresos
  esperados, y la gráfica de la curva de ingresos decodificada desde Base64.

---

## 3. Archivos clave

| Ruta                                                      | Propósito                                                 |
|-----------------------------------------------------------|-----------------------------------------------------------|
| `2/Financieras/Optimizacion_Precios_PyMC.py`              | Modelo PyMC reutilizable (regresión lineal o polinómica bayesiana) |
| `2/Financieras/backend/main.py`                           | API FastAPI que envuelve el helper PyMC                   |
| `2/Financieras/backend/requirements.txt`                  | Dependencias Python (versiones fijas)                     |
| `2/Financieras/backend/tests/test_price_optimization.py`  | Tests del modelo y la API                                 |
| `2/Financieras/backend/tests/conftest.py`                 | Fixtures compartidos (muestras sintéticas, mock de PyMC)  |
| `2/Financieras/pytest.ini`                                | Configuración de pytest (marcador `integration`)          |
| `2/Financieras/flutter_app/lib/main.dart`                 | UI principal Flutter                                      |
| `2/Financieras/flutter_app/lib/services/api_service.dart` | Cliente HTTP para la API                                  |
| `2/Financieras/flutter_app/lib/widgets/revenue_plot.dart` | Widget que decodifica y muestra la curva de ingresos PNG  |

---

## 4. Variables de Entorno

### Backend

| Variable            | Descripción                              | Default                             |
|---------------------|------------------------------------------|-------------------------------------|
| `ALLOWED_ORIGINS`   | Orígenes CORS separados por coma         | `http://localhost:3000`             |

A diferencia de Ciberseguridad, la configuración CORS está hardcodeada en `backend/main.py`.
`ALLOWED_ORIGINS` se parsea directamente sin valores por defecto adicionales.

### Flutter

| Variable         | Descripción                         | Default                       |
|------------------|-------------------------------------|-------------------------------|
| `API_BASE_URL`   | URL base del backend (archivo `.env`)| `http://127.0.0.1:8000`      |

---

## 5. Decisiones de Arquitectura

- **Decisión**: modelo de regresión lineal simple (ventas ~ precio) en vez de modelos más complejos.
  - **Razón**: el objetivo es encontrar un precio óptimo interpretable; la linealidad permite
    elasticidad constante y solución analítica aproximada.
  - **Consecuencia**: si la relación precio-demanda es no lineal, las predicciones pueden ser
    sesgadas. Revisar residuos en producción.

- **Decisión**: grid de precios generado automáticamente (100 puntos uniformes) cuando el usuario no
  lo especifica.
  - **Razón**: cubrir todo el rango observado sin forzar al cliente a definir la resolución.
  - **Consecuencia**: para rangos muy amplios, 100 puntos pueden ser excesivos o insuficientes
    según el caso de uso.

- **Decisión**: endpoint GET `/health` con versión y timestamp, separado del GET `/`.
  - **Razón**: monitoreo en producción necesita metadatos adicionales para verificar despliegues.
  - **Consecuencia**: dos endpoints de salud; `/` se mantiene como compatibilidad hacia atrás.

- **Decisión**: uso de `flutter_dotenv` en Flutter para la URL del backend.
  - **Razón**: evitar hardcodear la URL y permitir distintos entornos (local, staging, prod) sin
    recompilar.
  - **Consecuencia**: requiere archivo `.env` presente al arrancar la app.

- **Decisión**: middleware de logging en cada request (`log_requests`).
  - **Razón**: trazabilidad básica sin depender de servicios externos.
  - **Consecuencia**: overhead mínimo (~0.1ms) pero logs útiles para depuración.

---

## 6. Riesgos Conocidos

- **Riesgo**: modelo lineal puede no capturar elasticidad variable (demanda no lineal).
  - **Mitigación actual**: soporte de modelo polinómico bayesiano implementado
    (`model_type="polynomial"` con `degree` configurable) para demanda no lineal; el modelo lineal
    sigue siendo el default por interpretabilidad.
  - **Mitigación pendiente**: splines bayesianos (p. ej. `pm.gp`) para formas más flexibles sin
    fijar un grado; notificación en UI cuando `degree` se acerque al número de observaciones.

- **Riesgo**: inferencia bayesiana costosa en CPU bajo concurrencia.
  - **Mitigación actual**: límites estrictos en `draws` (max 10000) y `tune` (max 10000). Sin cola de jobs.
  - **Mitigación pendiente**: workers asíncronos con cola de tareas y rate limiting.

- **Riesgo**: `ALLOWED_ORIGINS` con un solo origen por defecto puede bloquear UIs legítimas.
  - **Mitigación actual**: variable de entorno para configurar según despliegue.
  - **Mitigación pendiente**: documentar la configuración multi-origen en producción.

- **Riesgo**: el grid automático de 100 puntos puede ser computacionalmente pesado si el rango es
  grande combinado con `draws` altos.
  - **Mitigación actual**: límite de `draws` a 10000. El grid se evalúa vectorizado.
  - **Mitigación pendiente**: permitir configurar la resolución del grid automático.

- **Riesgo**: cliente Flutter sin archivo `.env` falla silenciosamente con fallback a localhost.
  - **Mitigación actual**: fallback a `http://127.0.0.1:8000`.
  - **Mitigación pendiente**: mostrar advertencia en UI si el archivo `.env` no existe.

---

## 7. Smoke Tests

```bash
# 1. Health check simple
curl http://127.0.0.1:8000/
# → {"status":"ok"}

# 2. Health check detallado
curl http://127.0.0.1:8000/health
# → {"status":"ok","version":"1.0.0","timestamp":"2025-01-01T00:00:00"}

# 3. Optimización con payload mínimo (3 observaciones)
curl -X POST http://127.0.0.1:8000/optimise \
  -H "Content-Type: application/json" \
  -d '{
    "observations": [
      {"precio": 10, "ventas": 100},
      {"precio": 15, "ventas": 75},
      {"precio": 20, "ventas": 55}
    ],
    "draws": 500,
    "tune": 200
  }'

# 4. Validación: menos de 3 observaciones (400)
curl -X POST http://127.0.0.1:8000/optimise \
  -H "Content-Type: application/json" \
  -d '{"observations":[{"precio":10,"ventas":100},{"precio":15,"ventas":80}],"draws":500,"tune":200}'
# → {"detail":"Debe proporcionar al menos 3 observaciones de precio-venta."}
```

---

## 8. Pruebas

```bash
cd 2/Financieras
pip install -r backend/requirements.txt

# Tests unitarios y de integración
pytest -q backend/tests/ -v

# Solo tests de integración (requiere PyMC real instalado)
pytest -q backend/tests/ -v -m integration

# Con cobertura
pytest -q backend/tests/ --cov=backend --cov=Optimizacion_Precios_PyMC

# Flutter
cd flutter_app
flutter test
```

**Nota:** `conftest.py` mockea `pymc.sample` automáticamente cuando la biblioteca real no está
disponible. Los tests marcados como `integration` corren el sampler real y requieren PyMC instalado.

---

## 9. Troubleshooting

### CORS

Si el frontend reporta errores CORS, verificar que `ALLOWED_ORIGINS` incluya el origen exacto del
frontend. Para múltiples orígenes en producción:
```bash
export ALLOWED_ORIGINS="https://miapp.com,https://staging.miapp.com"
```

### PyMC / Matplotlib

El helper usa `matplotlib.use("Agg")`. Si aparece un error de backend, reinstalar:
```bash
pip install --force-reinstall matplotlib
```

### Conexión Flutter

- **Emulador Android**: `http://10.0.2.2:8000` en el `.env` (no `localhost`).
- **Dispositivo físico**: usar la IP de la máquina host.
- Si la app no encuentra el `.env`, crear uno con:
  ```env
  API_BASE_URL=http://10.0.2.2:8000
  ```

### Rendimiento

Reducir `draws` y `tune` durante desarrollo. Valores rápidos:
```json
{"draws": 500, "tune": 200}
```
Para producción: `draws=2000`, `tune=1000`, `target_accept=0.9`. Si el grid automático es muy denso,
pasar un `price_grid` explícito con 10–20 puntos.

### Errores de dependencias

Las dependencias del backend están fijadas con versiones exactas en `requirements.txt`. Si hay
conflictos con proyectos vecinos en el monorepo, usar un entorno virtual aislado.

---

## 10. Notas

- La pendiente negativa en `parameter_means` confirma elasticidad negativa (mayor precio → menor
  demanda). Si la pendiente estimada es positiva, revisar los datos de entrada.
- El helper expone `raw_trace` para diagnósticos de convergencia (R-hat, ESS, trazas).
- No hay endpoints `/metrics` — el monitoreo operativo se limita al logging middleware y al
  endpoint `/health`.
- No hay Dockerfile ni CI workflows definidos para este proyecto.
- Para interpretar la sensibilidad al precio: si la pendiente estimada es `-3.9`, cada unidad de
  precio adicional reduce las ventas esperadas en ~3.9 unidades.

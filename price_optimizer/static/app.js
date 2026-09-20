(function () {
  "use strict";

  var form = document.getElementById("optimisation-form");
  var observationsInput = document.getElementById("observations");
  var gridInput = document.getElementById("price-grid");
  var modelInput = document.getElementById("model-type");
  var degreeField = document.getElementById("degree-field");
  var degreeInput = document.getElementById("degree");
  var submitButton = document.getElementById("submit-button");
  var loadingState = document.getElementById("loading-state");
  var emptyState = document.getElementById("empty-state");
  var errorBanner = document.getElementById("error-banner");
  var resultsContent = document.getElementById("results-content");
  var modelSummary = document.getElementById("model-summary");
  var kpis = document.getElementById("kpis");
  var chartContainer = document.getElementById("chart-container");
  var parametersTable = document.getElementById("parameters-table");
  var resultsTable = document.getElementById("results-table");

  function parseNumber(value, label) {
    var number = Number(value);
    if (!value.trim() || !Number.isFinite(number)) {
      throw new Error(label + " debe contener números finitos.");
    }
    return number;
  }

  function parseObservations() {
    var lines = observationsInput.value.replace(/;/g, "\n").split(/\r?\n/).filter(function (line) { return line.trim(); });
    if (lines.length < 3) throw new Error("Debe proporcionar al menos 3 observaciones.");
    return lines.map(function (line, index) {
      var parts = line.trim().split(/\s*,\s*|\s+/).filter(Boolean);
      if (parts.length !== 2) throw new Error("La línea " + (index + 1) + " debe tener exactamente precio y ventas.");
      var precio = parseNumber(parts[0], "El precio de la línea " + (index + 1));
      var ventas = parseNumber(parts[1], "Las ventas de la línea " + (index + 1));
      if (precio <= 0) throw new Error("El precio debe ser mayor que cero (línea " + (index + 1) + ").");
      if (ventas < 0) throw new Error("Las ventas no pueden ser negativas (línea " + (index + 1) + ").");
      return { precio: precio, ventas: ventas };
    });
  }

  function parseGrid() {
    if (!gridInput.value.trim()) return null;
    var parts = gridInput.value.trim().split(/[\s,]+/).filter(Boolean);
    if (parts.length < 5) throw new Error("El grid de precios debe tener al menos 5 valores.");
    return parts.map(function (value) {
      var number = parseNumber(value, "El grid de precios");
      if (number <= 0) throw new Error("Los precios del grid deben ser mayores que cero.");
      return number;
    });
  }

  function boundedNumber(id, label, min, max) {
    var value = Number(document.getElementById(id).value);
    if (!Number.isInteger(value) && id !== "target-accept") throw new Error(label + " debe ser un número entero.");
    if (!Number.isFinite(value) || value < min || value > max) throw new Error(label + " debe estar entre " + min + " y " + max + ".");
    return value;
  }

  function requestPayload() {
    var observations = parseObservations();
    var payload = {
      observations: observations,
      draws: boundedNumber("draws", "Draws", 500, 10000),
      tune: boundedNumber("tune", "Tune", 200, 10000),
      target_accept: boundedNumber("target-accept", "Target accept", 0.5, 0.99),
      model_type: modelInput.value
    };
    var grid = parseGrid();
    if (grid) payload.price_grid = grid;
    if (modelInput.value === "polynomial") {
      payload.degree = boundedNumber("degree", "El grado", 1, 5);
      if (payload.degree >= observations.length) throw new Error("El grado debe ser menor que el número de observaciones.");
    }
    return payload;
  }

  function format(value, digits) {
    return Number(value).toLocaleString("es-AR", { maximumFractionDigits: digits === undefined ? 2 : digits });
  }

  function showError(message) {
    errorBanner.textContent = message;
    errorBanner.classList.remove("hidden");
    resultsContent.classList.add("hidden");
    emptyState.classList.add("hidden");
  }

  function apiError(detail) {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map(function (item) { return item.msg || "Error de validación"; }).join("; ");
    return "La solicitud no pudo procesarse.";
  }

  function createSvg(tag, attrs) {
    var svgNamespace = "http://www.w3.org/2000/svg";
    var node = document.createElementNS(svgNamespace, tag);
    Object.keys(attrs).forEach(function (key) { node.setAttribute(key, attrs[key]); });
    return node;
  }

  function drawChart(data, observations) {
    chartContainer.textContent = "";
    var svg = createSvg("svg", { viewBox: "0 0 720 400", role: "img", "aria-labelledby": "chart-title chart-description" });
    var title = createSvg("title", { id: "chart-title" }); title.textContent = "Ingresos por precio"; svg.appendChild(title);
    var description = createSvg("desc", { id: "chart-description" }); description.textContent = "Curva de ingresos esperados, observaciones y precio óptimo."; svg.appendChild(description);
    var left = 65, right = 690, top = 28, bottom = 345;
    var prices = data.price_grid, revenues = data.expected_revenue;
    var minPrice = Math.min.apply(null, prices), maxPrice = Math.max.apply(null, prices);
    var maxRevenue = Math.max.apply(null, revenues.concat(observations.map(function (o) { return o.precio * o.ventas; })));
    var targetStep = maxRevenue > 0 ? maxRevenue * 1.05 / 5 : 0;
    var niceStep = 1;
    if (targetStep > 0) {
      var magnitude = 10 ** Math.floor(Math.log10(targetStep));
      var normalized = targetStep / magnitude;
      var niceFactors = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10];
      niceStep = magnitude * (niceFactors.find(function (factor) { return factor >= normalized; }) || 10);
    }
    var maxY = niceStep * 5;
    var yDecimals = niceStep >= 1 ? 0 : niceStep >= 0.1 ? 1 : 2;
    function x(price) { return left + (price - minPrice) / (maxPrice - minPrice || 1) * (right - left); }
    function y(revenue) { return bottom - revenue / maxY * (bottom - top); }
    for (var i = 0; i <= 5; i += 1) {
      var gy = top + (bottom - top) * i / 5;
      svg.appendChild(createSvg("line", { x1: left, y1: gy, x2: right, y2: gy, class: "gridline" }));
      var tick = createSvg("text", { x: left - 8, y: gy + 4, class: "axis-text", "text-anchor": "end" });
      tick.textContent = format(niceStep * (5 - i), yDecimals); svg.appendChild(tick);
    }
    svg.appendChild(createSvg("line", { x1: left, y1: bottom, x2: right, y2: bottom, class: "axis" }));
    svg.appendChild(createSvg("line", { x1: left, y1: top, x2: left, y2: bottom, class: "axis" }));
    var points = prices.map(function (price, index) { return x(price) + "," + y(revenues[index]); }).join(" ");
    svg.appendChild(createSvg("polyline", { points: points, class: "revenue-line", fill: "none" }));
    observations.forEach(function (observation) {
      svg.appendChild(createSvg("circle", { cx: x(observation.precio), cy: y(observation.precio * observation.ventas), r: 4, class: "observation-point" }));
    });
    var optimalX = x(data.optimal_price);
    svg.appendChild(createSvg("line", { x1: optimalX, y1: top, x2: optimalX, y2: bottom, class: "optimal-line" }));
    var optimalLabel = createSvg("text", { x: optimalX + 5, y: top + 15, class: "optimal-label" }); optimalLabel.textContent = "óptimo"; svg.appendChild(optimalLabel);
    for (var xTick = 0; xTick <= 4; xTick += 1) {
      var price = minPrice + (maxPrice - minPrice) * xTick / 4;
      var priceTick = createSvg("text", { x: x(price), y: bottom + 18, class: "axis-text", "text-anchor": "middle" });
      priceTick.textContent = format(price, 2); svg.appendChild(priceTick);
    }
    var xLabel = createSvg("text", { x: (left + right) / 2, y: 385, class: "axis-label", "text-anchor": "middle" }); xLabel.textContent = "Precio"; svg.appendChild(xLabel);
    var yLabel = createSvg("text", { x: 15, y: (top + bottom) / 2, class: "axis-label", transform: "rotate(-90 15 " + ((top + bottom) / 2) + ")", "text-anchor": "middle" }); yLabel.textContent = "Ingresos"; svg.appendChild(yLabel);
    chartContainer.appendChild(svg);
  }

  function render(data, observations) {
    emptyState.classList.add("hidden"); errorBanner.classList.add("hidden"); resultsContent.classList.remove("hidden");
    modelSummary.textContent = "Modelo: " + (data.model_type === "polynomial" ? "Polinómico (grado " + data.degree + ")" : "Lineal");
    kpis.innerHTML = "<div class=\"kpi\"><span class=\"kpi-label\">Precio óptimo</span><span class=\"kpi-value\">$" + format(data.optimal_price) + "</span></div>" +
      "<div class=\"kpi\"><span class=\"kpi-label\">Ingreso esperado</span><span class=\"kpi-value\">$" + format(data.optimal_expected_revenue) + "</span></div>" +
      (data.model_type === "linear" ? "<div class=\"kpi\"><span class=\"kpi-label\">Elasticidad estimada (pendiente)</span><span class=\"kpi-value\">" + format(data.parameter_means.pendiente, 3) + "</span></div>" : "");
    var parameterRows = Object.keys(data.parameter_means).map(function (name) { return "<tr><td>" + name + "</td><td>" + format(data.parameter_means[name], 4) + "</td></tr>"; }).join("");
    parametersTable.innerHTML = "<table><thead><tr><th>Parámetro</th><th>Media posterior</th></tr></thead><tbody>" + parameterRows + "</tbody></table>";
    var resultRows = data.price_grid.map(function (price, index) { return "<tr><td>" + format(price) + "</td><td>" + format(data.expected_sales[index]) + "</td><td>" + format(data.expected_revenue[index]) + "</td></tr>"; }).join("");
    resultsTable.innerHTML = "<table><thead><tr><th>Precio</th><th>Ventas esperadas</th><th>Ingresos esperados</th></tr></thead><tbody>" + resultRows + "</tbody></table>";
    drawChart(data, observations);
  }

  modelInput.addEventListener("change", function () { degreeField.classList.toggle("hidden", modelInput.value !== "polynomial"); });
  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var observations;
    try { var payload = requestPayload(); observations = payload.observations; } catch (error) { showError(error.message); return; }
    submitButton.disabled = true; submitButton.textContent = "Calculando…"; loadingState.classList.remove("hidden"); errorBanner.classList.add("hidden");
    fetch("/optimise", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) })
      .then(function (response) { return response.json().then(function (body) { if (!response.ok) throw new Error(apiError(body.detail)); return body; }); })
      .then(function (data) { render(data, observations); })
      .catch(function (error) { showError(error.name === "TypeError" ? "No se pudo conectar con el servidor." : error.message); })
      .finally(function () { submitButton.disabled = false; submitButton.textContent = "Optimizar precio"; loadingState.classList.add("hidden"); });
  });
}());

import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

import 'services/api_service.dart';
import 'widgets/revenue_plot.dart';

void main() async {
  await dotenv.load(fileName: ".env");
  runApp(const OptimizacionPreciosApp());
}

class OptimizacionPreciosApp extends StatelessWidget {
  const OptimizacionPreciosApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Optimizacion de Precios PyMC',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.indigo),
        useMaterial3: true,
      ),
      home: const PriceFormPage(),
    );
  }
}

class PriceFormPage extends StatefulWidget {
  const PriceFormPage({super.key});

  @override
  State<PriceFormPage> createState() => _PriceFormPageState();
}

class _PriceFormPageState extends State<PriceFormPage> {
  final _formKey = GlobalKey<FormState>();
  final _dataController = TextEditingController(
    text:
        '10, 100\n12, 90\n15, 80\n18, 70\n20, 65\n22, 60\n25, 50\n28, 45\n30, 40\n35, 30',
  );
  final _priceGridController = TextEditingController(text: '');
  final _drawsController = TextEditingController(text: '2000');
  final _tuneController = TextEditingController(text: '1000');
  final _targetAcceptController = TextEditingController(text: '0.9');
  final _degreeController = TextEditingController(text: '2');
  final ApiService _apiService = ApiService(
    baseUrl: dotenv.env['API_BASE_URL'] ?? 'http://127.0.0.1:8000',
  );

  String _modelType = 'linear';
  PriceOptimisationResponse? _response;
  bool _isSubmitting = false;
  String? _errorMessage;

  @override
  void dispose() {
    _dataController.dispose();
    _priceGridController.dispose();
    _drawsController.dispose();
    _tuneController.dispose();
    _targetAcceptController.dispose();
    _degreeController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Optimizacion de precios con PyMC')),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Ingresa pares "precio, ventas". Usa comas o saltos de linea.',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _dataController,
                  minLines: 8,
                  maxLines: 16,
                  decoration: const InputDecoration(
                    labelText: 'Datos historicos de precio y ventas',
                    hintText: '10, 100',
                    border: OutlineInputBorder(),
                  ),
                  validator: (value) {
                    if (value == null || value.trim().isEmpty) {
                      return 'Debe ingresar datos.';
                    }
                    try {
                      _parsePairs(value);
                    } catch (error) {
                      return error.toString();
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: _priceGridController,
                  decoration: const InputDecoration(
                    labelText: 'Grid personalizado de precios (opcional)',
                    hintText: '8, 12, 16, 20, 24',
                    border: OutlineInputBorder(),
                  ),
                  validator: (value) {
                    if (value == null || value.trim().isEmpty) {
                      return null;
                    }
                    try {
                      _parseGrid(value);
                    } catch (error) {
                      return error.toString();
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 16),
                DropdownButtonFormField<String>(
                  initialValue: _modelType,
                  decoration: const InputDecoration(
                    labelText: 'Modelo de demanda',
                    border: OutlineInputBorder(),
                  ),
                  items: const [
                    DropdownMenuItem(value: 'linear', child: Text('Lineal')),
                    DropdownMenuItem(value: 'polynomial', child: Text('Polinómico')),
                  ],
                  onChanged: (value) {
                    setState(() {
                      _modelType = value ?? 'linear';
                    });
                  },
                  validator: (value) =>
                      value == null ? 'Seleccione un modelo.' : null,
                ),
                if (_modelType == 'polynomial') ...[
                  const SizedBox(height: 16),
                  _buildIntegerField('Grado del polinomio', _degreeController,
                      min: 1, max: 5),
                ],
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                        child: _buildIntegerField(
                            'Iteraciones (draws)', _drawsController,
                            min: 500)),
                    const SizedBox(width: 12),
                    Expanded(
                        child: _buildIntegerField(
                            'Calentamiento (tune)', _tuneController,
                            min: 200)),
                  ],
                ),
                const SizedBox(height: 12),
                _buildDoubleField('Target accept', _targetAcceptController,
                    min: 0.5, max: 0.99),
                const SizedBox(height: 24),
                FilledButton.icon(
                  onPressed: _isSubmitting ? null : _submit,
                  icon: _isSubmitting
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.price_change),
                  label: Text(
                      _isSubmitting ? 'Calculando...' : 'Optimizar precio'),
                ),
                const SizedBox(height: 16),
                if (_errorMessage != null)
                  Text(_errorMessage!,
                      style: const TextStyle(color: Colors.redAccent)),
                if (_response != null) ...[
                  const SizedBox(height: 16),
                  _buildSummaryCard(_response!),
                  const SizedBox(height: 16),
                  _buildDetailsTable(_response!),
                  const SizedBox(height: 24),
                  Text('Ingresos esperados por precio',
                      style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  RevenuePlot(base64Image: _response!.revenuePlotBase64),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSummaryCard(PriceOptimisationResponse response) {
    final textTheme = Theme.of(context).textTheme;
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Precio óptimo', style: textTheme.titleMedium),
            const SizedBox(height: 8),
            Text('Precio: ${response.optimalPrice.toStringAsFixed(2)}'),
            Text(
                'Ingreso esperado: ${response.optimalExpectedRevenue.toStringAsFixed(2)}'),
            const SizedBox(height: 12),
            Text('Medias de parámetros', style: textTheme.titleSmall),
            for (final entry in response.parameterMeans.entries)
              Text('${entry.key}: ${entry.value.toStringAsFixed(4)}'),
          ],
        ),
      ),
    );
  }

  Widget _buildDetailsTable(PriceOptimisationResponse response) {
    final rows = <DataRow>[];
    for (var i = 0; i < response.priceGrid.length; i++) {
      rows.add(
        DataRow(
          cells: [
            DataCell(Text(response.priceGrid[i].toStringAsFixed(2))),
            DataCell(Text(response.expectedSales[i].toStringAsFixed(2))),
            DataCell(Text(response.expectedRevenue[i].toStringAsFixed(2))),
          ],
        ),
      );
    }

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: DataTable(
        headingRowColor: MaterialStatePropertyAll(
            Theme.of(context).colorScheme.primary.withOpacity(0.08)),
        columns: const [
          DataColumn(label: Text('Precio')),
          DataColumn(label: Text('Ventas esperadas')),
          DataColumn(label: Text('Ingresos esperados')),
        ],
        rows: rows.take(12).toList(),
      ),
    );
  }

  Widget _buildIntegerField(String label, TextEditingController controller,
      {int? min, int? max}) {
    return TextFormField(
      controller: controller,
      keyboardType: TextInputType.number,
      decoration:
          InputDecoration(labelText: label, border: const OutlineInputBorder()),
      validator: (value) {
        if (value == null || value.trim().isEmpty) {
          return 'Requerido';
        }
        final parsed = int.tryParse(value);
        if (parsed == null) {
          return 'Debe ser un número entero';
        }
        if (min != null && parsed < min) {
          return 'Mínimo $min';
        }
        if (max != null && parsed > max) {
          return 'Máximo $max';
        }
        return null;
      },
    );
  }

  Widget _buildDoubleField(String label, TextEditingController controller,
      {double? min, double? max}) {
    return TextFormField(
      controller: controller,
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      decoration:
          InputDecoration(labelText: label, border: const OutlineInputBorder()),
      validator: (value) {
        if (value == null || value.trim().isEmpty) {
          return 'Requerido';
        }
        final parsed = double.tryParse(value);
        if (parsed == null) {
          return 'Debe ser un número';
        }
        if (min != null && parsed < min) {
          return 'Mínimo $min';
        }
        if (max != null && parsed > max) {
          return 'Máximo $max';
        }
        return null;
      },
    );
  }

  Future<void> _submit() async {
    final isValid = _formKey.currentState?.validate() ?? false;
    if (!isValid) {
      return;
    }

    late List<Map<String, double>> observations;
    late List<double>? priceGrid;

    try {
      observations = _parsePairs(_dataController.text);
      priceGrid = _priceGridController.text.trim().isEmpty
          ? null
          : _parseGrid(_priceGridController.text);
      if (priceGrid != null && priceGrid.length < 5) {
        throw const FormatException('El grid debe tener al menos 5 precios.');
      }
    } catch (error) {
      setState(() {
        _errorMessage = error.toString();
      });
      return;
    }

    final draws = int.parse(_drawsController.text);
    final tune = int.parse(_tuneController.text);
    final targetAccept = double.parse(_targetAcceptController.text);
    final degree = _modelType == 'polynomial' ? int.parse(_degreeController.text) : 2;

    setState(() {
      _isSubmitting = true;
      _errorMessage = null;
    });

    try {
      final response = await _apiService.optimise(
        observations: observations,
        priceGrid: priceGrid,
        draws: draws,
        tune: tune,
        targetAccept: targetAccept,
        modelType: _modelType,
        degree: degree,
      );
      setState(() {
        _response = response;
      });
    } catch (error) {
      setState(() {
        _errorMessage = error.toString();
        _response = null;
      });
    } finally {
      if (mounted) {
        setState(() {
          _isSubmitting = false;
        });
      }
    }
  }

  List<Map<String, double>> _parsePairs(String raw) {
    final lines = raw.split(RegExp(r'[\r\n;]+'))
      ..removeWhere((line) => line.trim().isEmpty);
    if (lines.length < 3) {
      throw const FormatException('Se requieren al menos tres observaciones.');
    }

    final observations = <Map<String, double>>[];
    for (final line in lines) {
      final parts = line.split(',').map((token) => token.trim()).toList();
      if (parts.length != 2) {
        throw FormatException('Cada línea debe tener 2 valores: "$line"');
      }
      final price = double.tryParse(parts[0]);
      final sales = double.tryParse(parts[1]);
      if (price == null || price <= 0) {
        throw FormatException('Precio inválido en la línea: "$line"');
      }
      if (sales == null || sales < 0) {
        throw FormatException('Ventas inválidas en la línea: "$line"');
      }
      observations.add({'precio': price, 'ventas': sales});
    }
    return observations;
  }

  List<double> _parseGrid(String raw) {
    final tokens = raw.split(RegExp(r'[\s,;]+'))
      ..removeWhere((token) => token.trim().isEmpty);
    if (tokens.length < 5) {
      throw const FormatException('Proporciona al menos 5 precios en el grid.');
    }
    final values = <double>[];
    for (final token in tokens) {
      final value = double.tryParse(token);
      if (value == null || value <= 0) {
        throw FormatException('Valor de precio inválido: "$token"');
      }
      values.add(value);
    }
    values.sort();
    return values;
  }
}

import 'dart:convert';

import 'package:http/http.dart' as http;

class PriceOptimisationResponse {
  PriceOptimisationResponse({
    required this.priceGrid,
    required this.expectedSales,
    required this.expectedRevenue,
    required this.optimalPrice,
    required this.optimalExpectedRevenue,
    required this.parameterMeans,
    required this.revenuePlotBase64,
    this.modelType = 'linear',
    this.degree = 2,
  });

  factory PriceOptimisationResponse.fromJson(Map<String, dynamic> json) {
    return PriceOptimisationResponse(
      priceGrid: (json['price_grid'] as List<dynamic>).map((value) => (value as num).toDouble()).toList(),
      expectedSales: (json['expected_sales'] as List<dynamic>).map((value) => (value as num).toDouble()).toList(),
      expectedRevenue: (json['expected_revenue'] as List<dynamic>).map((value) => (value as num).toDouble()).toList(),
      optimalPrice: (json['optimal_price'] as num).toDouble(),
      optimalExpectedRevenue: (json['optimal_expected_revenue'] as num).toDouble(),
      parameterMeans: (json['parameter_means'] as Map<String, dynamic>)
          .map((key, value) => MapEntry(key, (value as num).toDouble())),
      revenuePlotBase64: json['revenue_plot_base64'] as String,
      modelType: json['model_type'] as String? ?? 'linear',
      degree: json['degree'] as int? ?? 2,
    );
  }

  final List<double> priceGrid;
  final List<double> expectedSales;
  final List<double> expectedRevenue;
  final double optimalPrice;
  final double optimalExpectedRevenue;
  final Map<String, double> parameterMeans;
  final String revenuePlotBase64;
  final String modelType;
  final int degree;
}

class ApiService {
  ApiService({required this.baseUrl});

  final String baseUrl;

  Future<PriceOptimisationResponse> optimise({
    required List<Map<String, double>> observations,
    List<double>? priceGrid,
    int draws = 2000,
    int tune = 1000,
    double targetAccept = 0.9,
    String modelType = 'linear',
    int degree = 2,
  }) async {
    final uri = Uri.parse('$baseUrl/optimise');

    final payload = <String, dynamic>{
      'observations': observations,
      'draws': draws,
      'tune': tune,
      'target_accept': targetAccept,
      'model_type': modelType,
      'degree': degree,
    };
    if (priceGrid != null) {
      payload['price_grid'] = priceGrid;
    }

    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );

    if (response.statusCode >= 400) {
      throw Exception('Error del backend: ${_extractErrorMessage(response.body)}');
    }

    return PriceOptimisationResponse.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  String _extractErrorMessage(String body) {
    try {
      final decoded = jsonDecode(body) as Map<String, dynamic>;
      final detail = decoded['detail'];
      if (detail is String) {
        return detail;
      }
      if (detail is Map<String, dynamic> && detail['detail'] != null) {
        return detail['detail'].toString();
      }
    } catch (_) {}
    return body.isEmpty ? 'Respuesta vacía del servidor.' : body;
  }
}

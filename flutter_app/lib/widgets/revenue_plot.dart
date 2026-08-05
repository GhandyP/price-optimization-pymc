import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';

class RevenuePlot extends StatelessWidget {
  const RevenuePlot({super.key, required this.base64Image});

  final String base64Image;

  @override
  Widget build(BuildContext context) {
    if (base64Image.isEmpty) {
      return const Text('No hay grafica disponible.');
    }

    try {
      final Uint8List bytes = base64Decode(base64Image);
      return ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: Image.memory(bytes, fit: BoxFit.contain),
      );
    } catch (_) {
      return const Text('Error al decodificar la imagen.');
    }
  }
}

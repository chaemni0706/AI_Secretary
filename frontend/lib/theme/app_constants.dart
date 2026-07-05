import 'package:flutter/material.dart';

class AppSpacing {
  static const double screenPadding = 20;
  static const double sectionGap = 16;
  static const double cardGap = 8;
  static const double iconButton = 40;
  static const double compactIconButton = 36;
}

class AppRadii {
  static const double card = 18;
  static const double control = 12;
  static const double small = 10;
}

class AppTextStyles {
  static const TextStyle screenTitle = TextStyle(
    fontSize: 26,
    fontWeight: FontWeight.w700,
    letterSpacing: -0.5,
  );

  static const TextStyle sectionTitle = TextStyle(
    fontSize: 17,
    fontWeight: FontWeight.w700,
  );

  static const TextStyle cardTitle = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w600,
  );

  static const TextStyle meta = TextStyle(fontSize: 12);
}

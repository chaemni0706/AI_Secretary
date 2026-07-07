class ScheduleDateParser {
  const ScheduleDateParser._();

  static DateTime? parse(String input) {
    final value = input.trim();
    if (value.isEmpty) return null;

    if (RegExp(r'^\d{8}$').hasMatch(value)) {
      return _date(
        int.parse(value.substring(0, 4)),
        int.parse(value.substring(4, 6)),
        int.parse(value.substring(6, 8)),
      );
    }

    final parts = value
        .split(RegExp(r'[-./\s]+'))
        .where((part) => part.isNotEmpty)
        .toList();
    if (parts.length != 3) return null;

    final year = int.tryParse(parts[0]);
    final month = int.tryParse(parts[1]);
    final day = int.tryParse(parts[2]);
    if (year == null || month == null || day == null) return null;
    return _date(year, month, day);
  }

  static String? normalize(String input) {
    final parsed = parse(input);
    if (parsed == null) return null;
    return format(parsed);
  }

  static String format(DateTime date) {
    final month = date.month.toString().padLeft(2, '0');
    final day = date.day.toString().padLeft(2, '0');
    return '${date.year}-$month-$day';
  }

  static DateTime? _date(int year, int month, int day) {
    if (year < 1000 || month < 1 || month > 12 || day < 1 || day > 31) {
      return null;
    }
    final date = DateTime(year, month, day);
    if (date.year != year || date.month != month || date.day != day) {
      return null;
    }
    return date;
  }
}

/// 위젯 대시보드에서 사용하는 순수 데이터 모델.
/// UI(아이콘/색)나 목 데이터는 포함하지 않는다. (lib/data 참고)
library;

/// 위젯 크기.
enum WidgetSize { small, medium, large }

extension WidgetSizeX on WidgetSize {
  String get label {
    switch (this) {
      case WidgetSize.small:
        return 'S';
      case WidgetSize.medium:
        return 'M';
      case WidgetSize.large:
        return 'L';
    }
  }

  String get description {
    switch (this) {
      case WidgetSize.small:
        return '작게';
      case WidgetSize.medium:
        return '보통';
      case WidgetSize.large:
        return '크게';
    }
  }

  /// 2열 그리드에서 차지하는 가로 칸 수 (small=1, medium/large=2=전체폭).
  int get columnSpan => this == WidgetSize.small ? 1 : 2;
}

/// 대시보드에 추가할 수 있는 위젯 종류.
enum DashboardWidgetType {
  briefing,
  monthlyCalendar,
  weeklyCalendar,
  weather,
  budget,
  spendingAnalysis,
  preparation,
  todo,
  ocr,
  aiRecommendation,
  reservation,
}

DashboardWidgetType? dashboardWidgetTypeFromName(String name) {
  for (final t in DashboardWidgetType.values) {
    if (t.name == name) return t;
  }
  return null;
}

/// 대시보드에 배치된 위젯 한 개(종류 + 크기 + 고유 id).
class DashboardWidgetItem {
  final String id;
  final DashboardWidgetType type;
  final WidgetSize size;

  const DashboardWidgetItem({
    required this.id,
    required this.type,
    required this.size,
  });

  DashboardWidgetItem copyWith({WidgetSize? size}) {
    return DashboardWidgetItem(id: id, type: type, size: size ?? this.size);
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'type': type.name,
    'size': size.name,
  };

  static DashboardWidgetItem? fromJson(Map<String, dynamic> json) {
    final type = dashboardWidgetTypeFromName((json['type'] ?? '').toString());
    if (type == null) return null;
    final size = WidgetSize.values.firstWhere(
      (s) => s.name == (json['size'] ?? '').toString(),
      orElse: () => WidgetSize.medium,
    );
    return DashboardWidgetItem(
      id: (json['id'] ?? '').toString(),
      type: type,
      size: size,
    );
  }
}

import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/dashboard_widget_model.dart';
import 'widget_catalog.dart';

/// 위젯 대시보드 레이아웃(위치·크기·구성) 영속화 저장소.
/// shared_preferences 에 JSON 으로 저장하여 앱 재시작 후에도 유지한다.
class WidgetLayoutStore {
  WidgetLayoutStore._();
  static final WidgetLayoutStore instance = WidgetLayoutStore._();

  static const _key = 'dashboard_widget_layout_v1';

  int _seq = 0;

  /// 새 위젯 인스턴스용 고유 id.
  String newId(DashboardWidgetType type) {
    _seq++;
    return '${type.name}_${DateTime.now().microsecondsSinceEpoch}_$_seq';
  }

  /// 처음 사용하는 사용자를 위한 기본 레이아웃.
  List<DashboardWidgetItem> defaultLayout() {
    DashboardWidgetItem make(DashboardWidgetType type, WidgetSize size) =>
        DashboardWidgetItem(id: newId(type), type: type, size: size);

    return [
      make(DashboardWidgetType.briefing, WidgetSize.medium),
      make(DashboardWidgetType.weather, WidgetSize.small),
      make(DashboardWidgetType.ocr, WidgetSize.small),
      make(DashboardWidgetType.todo, WidgetSize.medium),
      make(DashboardWidgetType.monthlyCalendar, WidgetSize.large),
      make(DashboardWidgetType.budget, WidgetSize.medium),
    ];
  }

  Future<List<DashboardWidgetItem>> load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_key);
      if (raw == null || raw.isEmpty) return defaultLayout();
      final decoded = jsonDecode(raw);
      if (decoded is! List) return defaultLayout();
      final items = decoded
          .whereType<Map>()
          .map((e) => DashboardWidgetItem.fromJson(e.cast<String, dynamic>()))
          .whereType<DashboardWidgetItem>()
          // 카탈로그에 없는(구버전) 타입은 제외.
          .where((e) => WidgetCatalog.specs.containsKey(e.type))
          .toList();
      return items.isEmpty ? defaultLayout() : items;
    } catch (_) {
      return defaultLayout();
    }
  }

  Future<void> save(List<DashboardWidgetItem> items) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(
        _key,
        jsonEncode(items.map((e) => e.toJson()).toList()),
      );
    } catch (_) {
      // 저장 실패는 무시(다음 편집 시 재시도).
    }
  }
}

final widgetLayoutStore = WidgetLayoutStore.instance;

import 'package:flutter/material.dart';
import '../models/dashboard_widget_model.dart';
import '../theme/app_theme.dart';

/// 위젯 종류별 표시 메타데이터(제목/설명/아이콘/포인트색/지원 크기).
/// "위젯 추가" 목록과 카드 헤더에서 공통으로 사용한다.
class DashboardWidgetSpec {
  final DashboardWidgetType type;
  final String title;
  final String description;
  final IconData icon;
  final Color accent;
  final List<WidgetSize> supportedSizes;

  const DashboardWidgetSpec({
    required this.type,
    required this.title,
    required this.description,
    required this.icon,
    required this.accent,
    required this.supportedSizes,
  });

  WidgetSize get defaultSize => supportedSizes.first;
}

/// 위젯 카탈로그 (추가 가능한 11종).
class WidgetCatalog {
  WidgetCatalog._();

  static const Map<DashboardWidgetType, DashboardWidgetSpec> specs = {
    DashboardWidgetType.briefing: DashboardWidgetSpec(
      type: DashboardWidgetType.briefing,
      title: '오늘 요약',
      description: '오늘 일정·할 일·AI 브리핑',
      icon: Icons.wb_sunny_outlined,
      accent: AppTheme.purple,
      supportedSizes: [WidgetSize.medium],
    ),
    DashboardWidgetType.monthlyCalendar: DashboardWidgetSpec(
      type: DashboardWidgetType.monthlyCalendar,
      title: '월간 캘린더',
      description: '이번 달 일정 미리보기',
      icon: Icons.calendar_month_outlined,
      accent: AppTheme.blue,
      supportedSizes: [WidgetSize.large],
    ),
    DashboardWidgetType.weeklyCalendar: DashboardWidgetSpec(
      type: DashboardWidgetType.weeklyCalendar,
      title: '주간 캘린더',
      description: '이번 주 일정 요약',
      icon: Icons.view_week_outlined,
      accent: AppTheme.teal,
      supportedSizes: [WidgetSize.medium],
    ),
    DashboardWidgetType.weather: DashboardWidgetSpec(
      type: DashboardWidgetType.weather,
      title: '날씨',
      description: '오늘·주간 날씨',
      icon: Icons.cloud_outlined,
      accent: TossColors.blue500,
      supportedSizes: [WidgetSize.small, WidgetSize.medium],
    ),
    DashboardWidgetType.budget: DashboardWidgetSpec(
      type: DashboardWidgetType.budget,
      title: '가계부',
      description: '이번 달 지출·예산 사용률',
      icon: Icons.account_balance_wallet_outlined,
      accent: AppTheme.orange,
      supportedSizes: [WidgetSize.medium],
    ),
    DashboardWidgetType.spendingAnalysis: DashboardWidgetSpec(
      type: DashboardWidgetType.spendingAnalysis,
      title: '소비 분석',
      description: '소비 패턴·AI 코멘트',
      icon: Icons.pie_chart_outline,
      accent: TossColors.red,
      supportedSizes: [WidgetSize.medium],
    ),
    DashboardWidgetType.preparation: DashboardWidgetSpec(
      type: DashboardWidgetType.preparation,
      title: '준비물',
      description: '다음 일정 준비물',
      icon: Icons.backpack_outlined,
      accent: AppTheme.green,
      supportedSizes: [WidgetSize.small],
    ),
    DashboardWidgetType.todo: DashboardWidgetSpec(
      type: DashboardWidgetType.todo,
      title: '할 일',
      description: '오늘 할 일 목록',
      icon: Icons.checklist_outlined,
      accent: AppTheme.blue,
      supportedSizes: [WidgetSize.medium, WidgetSize.large],
    ),
    DashboardWidgetType.ocr: DashboardWidgetSpec(
      type: DashboardWidgetType.ocr,
      title: 'OCR 인증',
      description: '오늘 인증 필요 건수',
      icon: Icons.document_scanner_outlined,
      accent: AppTheme.purple,
      supportedSizes: [WidgetSize.small],
    ),
    DashboardWidgetType.aiRecommendation: DashboardWidgetSpec(
      type: DashboardWidgetType.aiRecommendation,
      title: 'AI 추천',
      description: '일정·예약 AI 추천',
      icon: Icons.auto_awesome,
      accent: TossColors.purple,
      supportedSizes: [WidgetSize.medium],
    ),
    DashboardWidgetType.reservation: DashboardWidgetSpec(
      type: DashboardWidgetType.reservation,
      title: '예약 후보 추천',
      description: '추천 예약 시간대',
      icon: Icons.event_available_outlined,
      accent: AppTheme.teal,
      supportedSizes: [WidgetSize.medium],
    ),
  };

  static DashboardWidgetSpec of(DashboardWidgetType type) => specs[type]!;

  /// 추가 목록에 표시할 순서.
  static const List<DashboardWidgetType> catalogOrder = [
    DashboardWidgetType.briefing,
    DashboardWidgetType.monthlyCalendar,
    DashboardWidgetType.weeklyCalendar,
    DashboardWidgetType.weather,
    DashboardWidgetType.budget,
    DashboardWidgetType.spendingAnalysis,
    DashboardWidgetType.preparation,
    DashboardWidgetType.todo,
    DashboardWidgetType.ocr,
    DashboardWidgetType.aiRecommendation,
    DashboardWidgetType.reservation,
  ];
}

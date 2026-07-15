import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/models/ledger_api_models.dart';
import 'package:frontend/models/ledger_mappers.dart';

/// LedgerReportMapper 단위 테스트.
/// 실행: `flutter test test/ledger_mappers_test.dart`
///
/// 대시보드 위젯(budget/spending)이 이 매퍼로 실데이터를 뽑으므로, 후보 키
/// 매핑·반올림·초과 판정·상세 포맷이 깨지면 위젯이 잘못 그려진다.
void main() {
  group('LedgerReportMapper', () {
    final report = LedgerReportDto.fromJson({
      'month': '2026-07',
      'summary': {'month_expense': 238500, 'month_income': 500000},
      'category_analysis': [
        {'category': '식비', 'amount': 120000, 'ratio': 50},
        {'category': '카페', 'amount': 60000, 'percent': 25},
      ],
      'budget_usage': [
        {'category': '카페', 'usage_rate': 84.0, 'spent': 42000, 'budget': 50000},
        {
          'category': '식비',
          'usage_rate': 110,
          'spent': 110000,
          'budget': 100000,
          'status': 'exceeded',
        },
      ],
      'briefing': {'title': '7월 리포트', 'message': '이번 달 지출이 늘었어요.'},
    });

    test('summary 에서 총지출/수입/잔액을 읽는다', () {
      expect(report.totalExpense, 238500);
      expect(report.totalIncome, 500000);
      // 명시적 balance 키가 없으면 income - expense 로 보정.
      expect(report.balance, 261500);
    });

    test('category_analysis → CategoryStat (여러 후보 키 + 색 키 매핑)', () {
      final cats = report.categoryStats();
      expect(cats.length, 2);
      expect(cats[0].name, '식비');
      expect(cats[0].amount, 120000);
      expect(cats[0].pct, 50); // 'ratio'
      expect(cats[0].catKey, 'food');
      expect(cats[1].pct, 25); // 'percent' 후보 키
      expect(cats[1].catKey, 'cafe');
    });

    test('budget_usage → BudgetStat (사용률 반올림·초과 판정·상세 포맷)', () {
      final budgets = report.budgetStats();
      expect(budgets.length, 2);
      expect(budgets[0].name, '카페');
      expect(budgets[0].pct, 84); // 84.0 반올림
      expect(budgets[0].over, isFalse); // 84% < 100, status 없음
      expect(budgets[0].detail, '42,000 / 50,000');
      // status=exceeded 또는 pct>=100 → 초과.
      expect(budgets[1].over, isTrue);
      expect(budgets[1].pct, 110);
      expect(budgets[1].detail, '110,000 / 100,000');
    });

    test('briefingBody 는 message 를 우선 추출한다', () {
      expect(report.briefingBody, '이번 달 지출이 늘었어요.');
    });

    test('빈/누락 필드는 안전하게 기본값으로 처리한다', () {
      final empty = LedgerReportDto.fromJson({});
      expect(empty.totalExpense, 0);
      expect(empty.categoryStats(), isEmpty);
      expect(empty.budgetStats(), isEmpty);
      expect(empty.briefingBody, isNull);
    });
  });
}

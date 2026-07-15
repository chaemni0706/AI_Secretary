import 'package:flutter/material.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';

/// 탭하면 달력/시간 선택기를 여는 읽기 전용 입력 필드.
///
/// 일정 수정 화면과 할 일 추가 화면이 날짜/시간 선택 UI를 공통으로 쓰기 위해
/// 분리했다(반복 UI 위젯화). 사용자가 직접 텍스트를 입력하지 않고, 탭 시
/// [onTap] 에서 `showDatePicker` / `showTimePicker` 를 띄운 뒤 값을 채운다.
class PickerField extends StatelessWidget {
  final IconData icon;
  final String label;

  /// 표시할 선택값. null/빈 값이면 [hint] 를 흐리게 표시한다.
  final String? value;
  final String hint;
  final VoidCallback onTap;

  /// 값 지우기 콜백(선택 항목용). null 이면 지우기 버튼을 표시하지 않는다.
  final VoidCallback? onClear;

  const PickerField({
    super.key,
    required this.icon,
    required this.label,
    required this.value,
    required this.onTap,
    this.hint = '선택 안 함',
    this.onClear,
  });

  @override
  Widget build(BuildContext context) {
    final hasValue = value != null && value!.trim().isNotEmpty;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppRadii.control),
        child: InputDecorator(
          decoration: InputDecoration(
            labelText: label,
            prefixIcon: Icon(icon, size: 20),
            suffixIcon: (hasValue && onClear != null)
                ? IconButton(
                    icon: const Icon(Icons.clear, size: 18),
                    onPressed: onClear,
                    tooltip: '지우기',
                  )
                : const Icon(Icons.arrow_drop_down),
            filled: true,
            fillColor: Colors.white.withValues(alpha: 0.7),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(AppRadii.control),
              borderSide: BorderSide(color: AppTheme.separator),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(AppRadii.control),
              borderSide: BorderSide(color: AppTheme.separator),
            ),
          ),
          child: Text(
            hasValue ? value! : hint,
            style: TextStyle(
              fontSize: 15,
              color: hasValue ? AppTheme.textPrimary : AppTheme.textSecondary,
            ),
          ),
        ),
      ),
    );
  }
}

/// 날짜/시간 선택 헬퍼. 앱 어디서든 동일한 규칙(포맷·초기값)으로 선택기를
/// 띄우기 위해 모아둔다. 반환 포맷은 백엔드 계약과 동일하게 날짜 "YYYY-MM-DD",
/// 시간 "HH:mm" 이다.
class DateTimePickers {
  DateTimePickers._();

  static String formatDate(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-'
      '${d.month.toString().padLeft(2, '0')}-'
      '${d.day.toString().padLeft(2, '0')}';

  static String formatTime(TimeOfDay t) =>
      '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';

  /// "YYYY-MM-DD" 문자열을 DateTime 으로(파싱 실패 시 null).
  static DateTime? parseDate(String? ymd) {
    if (ymd == null || ymd.trim().isEmpty) return null;
    try {
      return DateTime.parse(ymd.trim());
    } catch (_) {
      return null;
    }
  }

  /// "HH:mm" 문자열을 TimeOfDay 로(파싱 실패 시 null).
  static TimeOfDay? parseTime(String? hhmm) {
    if (hhmm == null || hhmm.trim().isEmpty) return null;
    final m = RegExp(r'^(\d{1,2}):(\d{2})$').firstMatch(hhmm.trim());
    if (m == null) return null;
    final h = int.parse(m.group(1)!);
    final min = int.parse(m.group(2)!);
    if (h < 0 || h > 23 || min < 0 || min > 59) return null;
    return TimeOfDay(hour: h, minute: min);
  }

  /// 달력 선택기를 띄우고 선택된 날짜를 "YYYY-MM-DD" 로 반환(취소 시 null).
  ///
  /// [initial] 이 있으면 그 날짜를, 없으면 오늘을 초기 선택으로 연다.
  /// [firstDate] 미지정 시 5년 전 ~ 5년 후 범위로 연다.
  static Future<String?> pickDate(
    BuildContext context, {
    String? initial,
    DateTime? firstDate,
    DateTime? lastDate,
  }) async {
    final now = DateTime.now();
    final init = parseDate(initial) ?? now;
    final picked = await showDatePicker(
      context: context,
      initialDate: init,
      firstDate: firstDate ?? DateTime(now.year - 5),
      lastDate: lastDate ?? DateTime(now.year + 5),
      helpText: '날짜 선택',
      cancelText: '취소',
      confirmText: '확인',
    );
    return picked == null ? null : formatDate(picked);
  }

  /// 시간 선택기를 띄우고 선택된 시각을 "HH:mm" 로 반환(취소 시 null).
  static Future<String?> pickTime(
    BuildContext context, {
    String? initial,
  }) async {
    final init = parseTime(initial) ?? TimeOfDay.now();
    final picked = await showTimePicker(
      context: context,
      initialTime: init,
      helpText: '시간 선택',
      cancelText: '취소',
      confirmText: '확인',
      builder: (ctx, child) => MediaQuery(
        // 24시간 표기로 고정(HH:mm 계약과 일치).
        data: MediaQuery.of(ctx).copyWith(alwaysUse24HourFormat: true),
        child: child!,
      ),
    );
    return picked == null ? null : formatTime(picked);
  }
}

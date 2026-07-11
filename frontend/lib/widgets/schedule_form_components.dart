import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:table_calendar/table_calendar.dart';
import '../core/utils/schedule_date_parser.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../theme/schedule_styles.dart';
import 'glass_card.dart';

class ScheduleFormSection extends StatelessWidget {
  final List<Widget> children;

  const ScheduleFormSection({super.key, required this.children});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sectionGap),
      child: GlassCard(
        padding: EdgeInsets.zero,
        child: Column(children: children),
      ),
    );
  }
}

class ScheduleFormRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final Widget child;
  final bool showDivider;

  const ScheduleFormRow({
    super.key,
    required this.icon,
    required this.label,
    required this.child,
    this.showDivider = true,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Icon(icon, size: 20, color: AppTheme.textSecondary),
              const SizedBox(width: 12),
              SizedBox(
                width: 78,
                child: Text(
                  label,
                  style: AppTextStyles.cardTitle.copyWith(
                    color: AppTheme.textPrimary,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(child: child),
            ],
          ),
        ),
        if (showDivider)
          Divider(
            height: 1,
            indent: 58,
            color: AppTheme.separator.withValues(alpha: 0.7),
          ),
      ],
    );
  }
}

class ScheduleTextFieldRow extends StatelessWidget {
  final TextEditingController controller;
  final String label;
  final String? hint;
  final IconData icon;
  final int maxLines;
  final bool showDivider;

  const ScheduleTextFieldRow({
    super.key,
    required this.controller,
    required this.label,
    required this.icon,
    this.hint,
    this.maxLines = 1,
    this.showDivider = true,
  });

  @override
  Widget build(BuildContext context) {
    return ScheduleFormRow(
      icon: icon,
      label: label,
      showDivider: showDivider,
      child: TextField(
        controller: controller,
        maxLines: maxLines,
        style: AppTextStyles.cardTitle.copyWith(color: AppTheme.textPrimary),
        decoration: InputDecoration(
          hintText: hint,
          isDense: true,
          border: InputBorder.none,
          hintStyle: AppTextStyles.cardTitle.copyWith(
            color: AppTheme.textSecondary.withValues(alpha: 0.7),
          ),
        ),
      ),
    );
  }
}

class ScheduleDateTimeRow extends StatelessWidget {
  final String label;
  final IconData icon;
  final TextEditingController controller;
  final String hint;
  final bool showDivider;

  const ScheduleDateTimeRow({
    super.key,
    required this.label,
    required this.icon,
    required this.controller,
    required this.hint,
    this.showDivider = true,
  });

  @override
  Widget build(BuildContext context) {
    return ScheduleFormRow(
      icon: icon,
      label: label,
      showDivider: showDivider,
      child: Align(
        alignment: Alignment.centerLeft,
        child: Container(
          constraints: const BoxConstraints(minHeight: 34),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: AppTheme.blue.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(999),
          ),
          child: TextField(
            controller: controller,
            style: AppTextStyles.cardTitle.copyWith(color: AppTheme.blue),
            decoration: InputDecoration(
              hintText: hint,
              isDense: true,
              border: InputBorder.none,
              hintStyle: AppTextStyles.cardTitle.copyWith(
                color: AppTheme.blue.withValues(alpha: 0.62),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class ScheduleDatePickerRow extends StatelessWidget {
  final TextEditingController controller;
  final bool expanded;
  final DateTime focusedDay;
  final ValueChanged<bool> onExpandedChanged;
  final ValueChanged<DateTime> onFocusedDayChanged;
  final ValueChanged<DateTime> onDateSelected;
  final VoidCallback onNormalize;
  final bool showDivider;

  const ScheduleDatePickerRow({
    super.key,
    required this.controller,
    required this.expanded,
    required this.focusedDay,
    required this.onExpandedChanged,
    required this.onFocusedDayChanged,
    required this.onDateSelected,
    required this.onNormalize,
    this.showDivider = true,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        ScheduleFormRow(
          icon: Icons.event_outlined,
          label: '날짜',
          showDivider: false,
          child: GestureDetector(
            onTap: () => onExpandedChanged(!expanded),
            behavior: HitTestBehavior.opaque,
            child: Row(
              children: [
                Expanded(
                  child: Container(
                    constraints: const BoxConstraints(minHeight: 34),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 8,
                    ),
                    decoration: BoxDecoration(
                      color: AppTheme.blue.withValues(alpha: 0.08),
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: TextField(
                      controller: controller,
                      onTap: () => onExpandedChanged(true),
                      onSubmitted: (_) => onNormalize(),
                      onEditingComplete: onNormalize,
                      style: AppTextStyles.cardTitle.copyWith(
                        color: AppTheme.blue,
                      ),
                      decoration: InputDecoration(
                        hintText: 'YYYY-MM-DD',
                        isDense: true,
                        border: InputBorder.none,
                        hintStyle: AppTextStyles.cardTitle.copyWith(
                          color: AppTheme.blue.withValues(alpha: 0.62),
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Icon(
                  expanded
                      ? Icons.keyboard_arrow_up_rounded
                      : Icons.keyboard_arrow_down_rounded,
                  color: AppTheme.textSecondary,
                ),
              ],
            ),
          ),
        ),
        AnimatedCrossFade(
          firstChild: const SizedBox.shrink(),
          secondChild: InlineCalendarPicker(
            selectedDate: ScheduleDateParser.parse(controller.text),
            focusedDay: focusedDay,
            onFocusedDayChanged: onFocusedDayChanged,
            onDateSelected: onDateSelected,
          ),
          crossFadeState: expanded
              ? CrossFadeState.showSecond
              : CrossFadeState.showFirst,
          duration: const Duration(milliseconds: 180),
          sizeCurve: Curves.easeOut,
        ),
        if (showDivider)
          Divider(
            height: 1,
            indent: 58,
            color: AppTheme.separator.withValues(alpha: 0.7),
          ),
      ],
    );
  }
}

class InlineCalendarPicker extends StatelessWidget {
  final DateTime? selectedDate;
  final DateTime focusedDay;
  final ValueChanged<DateTime> onFocusedDayChanged;
  final ValueChanged<DateTime> onDateSelected;

  const InlineCalendarPicker({
    super.key,
    required this.selectedDate,
    required this.focusedDay,
    required this.onFocusedDayChanged,
    required this.onDateSelected,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(14, 0, 14, 12),
      child: Container(
        padding: const EdgeInsets.fromLTRB(8, 6, 8, 10),
        decoration: BoxDecoration(
          color: AppTheme.background.withValues(alpha: 0.68),
          borderRadius: BorderRadius.circular(AppRadii.control),
          border: Border.all(color: AppTheme.separator.withValues(alpha: 0.7)),
        ),
        child: TableCalendar(
          firstDay: DateTime.utc(2024, 1, 1),
          lastDay: DateTime.utc(2028, 12, 31),
          focusedDay: focusedDay,
          selectedDayPredicate: (day) =>
              selectedDate != null && isSameDay(day, selectedDate),
          calendarFormat: CalendarFormat.month,
          availableCalendarFormats: const {CalendarFormat.month: ''},
          headerStyle: HeaderStyle(
            formatButtonVisible: false,
            titleCentered: true,
            titleTextStyle: AppTextStyles.cardTitle.copyWith(
              color: AppTheme.textPrimary,
              fontSize: 15,
            ),
            leftChevronIcon: const Icon(
              Icons.chevron_left,
              color: AppTheme.textPrimary,
            ),
            rightChevronIcon: const Icon(
              Icons.chevron_right,
              color: AppTheme.textPrimary,
            ),
          ),
          daysOfWeekHeight: 26,
          rowHeight: 36,
          onPageChanged: onFocusedDayChanged,
          onDaySelected: (selected, focused) {
            onFocusedDayChanged(focused);
            onDateSelected(selected);
          },
          calendarStyle: CalendarStyle(
            todayDecoration: BoxDecoration(
              color: AppTheme.blue.withValues(alpha: 0.14),
              shape: BoxShape.circle,
            ),
            todayTextStyle: const TextStyle(
              color: AppTheme.blue,
              fontWeight: FontWeight.w700,
            ),
            selectedDecoration: const BoxDecoration(
              color: AppTheme.blue,
              shape: BoxShape.circle,
            ),
            selectedTextStyle: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w800,
            ),
            defaultTextStyle: const TextStyle(
              color: AppTheme.textPrimary,
              fontSize: 13,
            ),
            weekendTextStyle: const TextStyle(
              color: AppTheme.red,
              fontSize: 13,
            ),
            outsideTextStyle: TextStyle(
              color: AppTheme.textSecondary.withValues(alpha: 0.45),
              fontSize: 13,
            ),
          ),
        ),
      ),
    );
  }
}

class ScheduleTimePickerRow extends StatelessWidget {
  final TextEditingController controller;
  final String label;
  final IconData icon;
  final bool expanded;
  final ValueChanged<bool> onExpandedChanged;
  final ValueChanged<String> onTimeSelected;
  final bool enabled;
  final bool showDivider;

  const ScheduleTimePickerRow({
    super.key,
    required this.controller,
    required this.label,
    required this.icon,
    required this.expanded,
    required this.onExpandedChanged,
    required this.onTimeSelected,
    this.enabled = true,
    this.showDivider = true,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        ScheduleFormRow(
          icon: icon,
          label: label,
          showDivider: false,
          child: GestureDetector(
            onTap: enabled ? () => onExpandedChanged(!expanded) : null,
            behavior: HitTestBehavior.opaque,
            child: Row(
              children: [
                TimeSelectionChip(
                  label: controller.text.trim().isEmpty
                      ? 'HH:mm'
                      : controller.text.trim(),
                  selected: controller.text.trim().isNotEmpty,
                  enabled: enabled,
                ),
                const Spacer(),
                Icon(
                  expanded
                      ? Icons.keyboard_arrow_up_rounded
                      : Icons.keyboard_arrow_down_rounded,
                  color: enabled
                      ? AppTheme.textSecondary
                      : AppTheme.textSecondary.withValues(alpha: 0.45),
                ),
              ],
            ),
          ),
        ),
        AnimatedCrossFade(
          firstChild: const SizedBox.shrink(),
          secondChild: InlineTimePicker(
            selectedTime: controller.text,
            onTimeSelected: onTimeSelected,
          ),
          crossFadeState: expanded && enabled
              ? CrossFadeState.showSecond
              : CrossFadeState.showFirst,
          duration: const Duration(milliseconds: 180),
          sizeCurve: Curves.easeOut,
        ),
        if (showDivider)
          Divider(
            height: 1,
            indent: 58,
            color: AppTheme.separator.withValues(alpha: 0.7),
          ),
      ],
    );
  }
}

/// iOS 캘린더 스타일 시간 휠 선택기(오전/오후 + 시 + 5분 단위 분).
/// [ScheduleFormComponents]/[TodoFormComponents] 양쪽에서 공용으로 쓴다.
class InlineTimePicker extends StatelessWidget {
  final String selectedTime;
  final ValueChanged<String> onTimeSelected;

  const InlineTimePicker({
    super.key,
    required this.selectedTime,
    required this.onTimeSelected,
  });

  DateTime _initialDateTime() {
    final now = DateTime.now();
    final match = RegExp(
      r'^(\d{1,2}):(\d{2})$',
    ).firstMatch(selectedTime.trim());
    if (match == null) {
      final roundedMinute = (now.minute / 5).round() * 5 % 60;
      return DateTime(now.year, now.month, now.day, now.hour, roundedMinute);
    }
    final hour = int.parse(match.group(1)!);
    final minute = int.parse(match.group(2)!);
    return DateTime(now.year, now.month, now.day, hour, minute);
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(14, 0, 14, 12),
      child: Container(
        decoration: BoxDecoration(
          color: AppTheme.background.withValues(alpha: 0.68),
          borderRadius: BorderRadius.circular(AppRadii.control),
          border: Border.all(color: AppTheme.separator.withValues(alpha: 0.7)),
        ),
        height: 216,
        child: CupertinoDatePicker(
          mode: CupertinoDatePickerMode.time,
          backgroundColor: Colors.transparent,
          use24hFormat: false,
          minuteInterval: 5,
          initialDateTime: _initialDateTime(),
          onDateTimeChanged: (value) {
            final hh = value.hour.toString().padLeft(2, '0');
            final mm = value.minute.toString().padLeft(2, '0');
            onTimeSelected('$hh:$mm');
          },
        ),
      ),
    );
  }
}

class TimeSelectionChip extends StatelessWidget {
  final String label;
  final bool selected;
  final bool enabled;

  const TimeSelectionChip({
    super.key,
    required this.label,
    this.selected = false,
    this.enabled = true,
  });

  @override
  Widget build(BuildContext context) {
    final foreground = selected ? Colors.white : AppTheme.blue;
    final background = selected
        ? AppTheme.blue
        : AppTheme.blue.withValues(alpha: enabled ? 0.08 : 0.04);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: selected
              ? AppTheme.blue
              : AppTheme.blue.withValues(alpha: enabled ? 0.18 : 0.06),
        ),
      ),
      child: Text(
        label,
        style: AppTextStyles.cardTitle.copyWith(
          color: enabled
              ? foreground
              : AppTheme.textSecondary.withValues(alpha: 0.48),
        ),
      ),
    );
  }
}

class ScheduleCategorySelector extends StatelessWidget {
  final String value;
  final ValueChanged<String> onChanged;
  final bool showDivider;

  const ScheduleCategorySelector({
    super.key,
    required this.value,
    required this.onChanged,
    this.showDivider = true,
  });

  @override
  Widget build(BuildContext context) {
    return ScheduleFormRow(
      icon: Icons.category_outlined,
      label: '카테고리',
      showDivider: showDivider,
      child: Wrap(
        spacing: 8,
        runSpacing: 8,
        children: ScheduleStyles.categoryOrder.map((category) {
          final selected = category == value;
          final color = ScheduleStyles.categoryColor(category);
          return ChoiceChip(
            label: Text(category),
            selected: selected,
            showCheckmark: false,
            labelStyle: AppTextStyles.meta.copyWith(
              color: selected ? Colors.white : color,
              fontWeight: FontWeight.w700,
            ),
            selectedColor: color,
            backgroundColor: color.withValues(alpha: 0.1),
            side: BorderSide(color: color.withValues(alpha: 0.22)),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(999),
            ),
            onSelected: (_) => onChanged(category),
          );
        }).toList(),
      ),
    );
  }
}

class ScheduleDisabledOptionRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final bool showDivider;

  const ScheduleDisabledOptionRow({
    super.key,
    required this.icon,
    required this.label,
    required this.value,
    this.showDivider = true,
  });

  @override
  Widget build(BuildContext context) {
    return ScheduleFormRow(
      icon: icon,
      label: label,
      showDivider: showDivider,
      child: Text(
        value,
        textAlign: TextAlign.right,
        style: AppTextStyles.cardTitle.copyWith(
          color: AppTheme.textSecondary.withValues(alpha: 0.78),
        ),
      ),
    );
  }
}

/// 켜고 끌 수 있는 옵션 행(예: 하루 종일). 우측에 Switch 를 둔다.
class ScheduleToggleOptionRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool value;
  final ValueChanged<bool> onChanged;
  final bool showDivider;

  const ScheduleToggleOptionRow({
    super.key,
    required this.icon,
    required this.label,
    required this.value,
    required this.onChanged,
    this.showDivider = true,
  });

  @override
  Widget build(BuildContext context) {
    return ScheduleFormRow(
      icon: icon,
      label: label,
      showDivider: showDivider,
      child: Align(
        alignment: Alignment.centerRight,
        child: Switch.adaptive(
          value: value,
          activeColor: AppTheme.blue,
          onChanged: onChanged,
        ),
      ),
    );
  }
}

class ScheduleFormSubmitButton extends StatelessWidget {
  final bool saving;
  final String label;
  final VoidCallback? onPressed;

  const ScheduleFormSubmitButton({
    super.key,
    required this.saving,
    required this.label,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: FilledButton(
        onPressed: saving ? null : onPressed,
        style: FilledButton.styleFrom(
          backgroundColor: AppTheme.blue,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(vertical: 15),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppRadii.control),
          ),
        ),
        child: saving
            ? const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: Colors.white,
                ),
              )
            : Text(label),
      ),
    );
  }
}

import 'package:flutter/material.dart';
import '../core/utils/schedule_date_parser.dart';
import '../models/schedule_model.dart';
import '../services/api_client.dart';
import '../services/dashboard_api.dart';
import '../services/schedule_api.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../theme/schedule_styles.dart';
import '../widgets/schedule_form_components.dart';

class ScheduleFormScreen extends StatefulWidget {
  final ScheduleModel? initialSchedule;
  final String? initialDate;

  const ScheduleFormScreen({super.key, this.initialSchedule, this.initialDate});

  bool get isEditMode => initialSchedule != null;

  @override
  State<ScheduleFormScreen> createState() => _ScheduleFormScreenState();
}

class _ScheduleFormScreenState extends State<ScheduleFormScreen> {
  final _titleController = TextEditingController();
  final _startDateController = TextEditingController();
  final _endDateController = TextEditingController();
  final _startTimeController = TextEditingController();
  final _endTimeController = TextEditingController();
  final _locationController = TextEditingController();
  final _memoController = TextEditingController();

  String _category = ScheduleStyles.categoryOrder.last;
  String _priority = 'medium';
  bool _isAllDay = false;
  bool _saving = false;
  bool _startDatePickerOpen = false;
  bool _endDatePickerOpen = false;
  bool _startTimePickerOpen = false;
  bool _endTimePickerOpen = false;
  DateTime _focusedDate = DateTime.now();

  bool get _isEditMode => widget.initialSchedule != null;

  @override
  void initState() {
    super.initState();
    final schedule = widget.initialSchedule;
    if (schedule == null) {
      _startDateController.text = widget.initialDate ?? '';
      _endDateController.text = widget.initialDate ?? '';
      _focusedDate =
          ScheduleDateParser.parse(_startDateController.text) ?? DateTime.now();
      return;
    }
    _titleController.text = schedule.title;
    _startDateController.text = schedule.date ?? '';
    _endDateController.text = schedule.effectiveEndDate ?? schedule.date ?? '';
    _startTimeController.text = schedule.startTime ?? '';
    _endTimeController.text = schedule.endTime ?? '';
    _locationController.text = schedule.location ?? '';
    _memoController.text = ScheduleModel.stripEndDateToken(schedule.memo);
    _category = ScheduleStyles.categoryLabel(schedule.category);
    _priority = schedule.priority;
    _isAllDay = schedule.isAllDay;
    _focusedDate =
        ScheduleDateParser.parse(_startDateController.text) ?? DateTime.now();
  }

  @override
  void dispose() {
    _titleController.dispose();
    _startDateController.dispose();
    _endDateController.dispose();
    _startTimeController.dispose();
    _endTimeController.dispose();
    _locationController.dispose();
    _memoController.dispose();
    super.dispose();
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  int? _minutesOfDay(String value) {
    final match = RegExp(r'^(\d{1,2}):(\d{2})$').firstMatch(value.trim());
    if (match == null) return null;
    final hour = int.tryParse(match.group(1)!);
    final minute = int.tryParse(match.group(2)!);
    if (hour == null || minute == null) return null;
    if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return null;
    return hour * 60 + minute;
  }

  bool _isTimeOrderValid() {
    final start = _startTimeController.text.trim();
    final end = _endTimeController.text.trim();
    if (start.isEmpty || end.isEmpty) return true;
    final startMinutes = _minutesOfDay(start);
    final endMinutes = _minutesOfDay(end);
    if (startMinutes == null || endMinutes == null) return true;
    return startMinutes <= endMinutes;
  }

  /// 종료 날짜가 시작 날짜보다 빠르면 무효. 같은 날이면(하루 종일이 아닐 때)
  /// 시간 순서까지 확인하고, 종료일이 시작일보다 뒤(여러 날짜 일정)면 시간
  /// 비교는 의미가 없으므로 건너뛴다.
  bool _isDateOrderValid() {
    final start = _startDateController.text.trim();
    final end = _endDateController.text.trim();
    if (start.isEmpty || end.isEmpty) return true;
    final cmp = end.compareTo(start);
    if (cmp < 0) return false;
    if (cmp == 0 && !_isAllDay) return _isTimeOrderValid();
    return true;
  }

  void _closePickersExcept(String target) {
    setState(() {
      final openingStartDate = target == 'startDate' ? !_startDatePickerOpen : false;
      final openingEndDate = target == 'endDate' ? !_endDatePickerOpen : false;
      _startDatePickerOpen = openingStartDate;
      _endDatePickerOpen = openingEndDate;
      _startTimePickerOpen = target == 'startTime' ? !_startTimePickerOpen : false;
      _endTimePickerOpen = target == 'endTime' ? !_endTimePickerOpen : false;
      if (openingStartDate) {
        _focusedDate =
            ScheduleDateParser.parse(_startDateController.text) ?? _focusedDate;
      } else if (openingEndDate) {
        _focusedDate =
            ScheduleDateParser.parse(_endDateController.text) ?? _focusedDate;
      }
    });
  }

  bool _normalizeStartDateInput({bool showError = false}) {
    final normalized = ScheduleDateParser.normalize(_startDateController.text);
    if (normalized == null) {
      if (showError) _showMessage('시작 날짜 형식을 확인해 주세요.');
      return false;
    }
    final oldStart = _startDateController.text.trim();
    final endFollowsStart = _endDateController.text.trim().isEmpty ||
        _endDateController.text.trim() == oldStart;
    _startDateController.text = normalized;
    if (endFollowsStart) _endDateController.text = normalized;
    _focusedDate = ScheduleDateParser.parse(normalized) ?? _focusedDate;
    return true;
  }

  bool _normalizeEndDateInput({bool showError = false}) {
    final normalized = ScheduleDateParser.normalize(_endDateController.text);
    if (normalized == null) {
      if (showError) _showMessage('종료 날짜 형식을 확인해 주세요.');
      return false;
    }
    _endDateController.text = normalized;
    _focusedDate = ScheduleDateParser.parse(normalized) ?? _focusedDate;
    return true;
  }

  void _selectStartDate(DateTime date) {
    setState(() {
      final oldStart = _startDateController.text.trim();
      final endFollowsStart = _endDateController.text.trim().isEmpty ||
          _endDateController.text.trim() == oldStart;
      _startDateController.text = ScheduleDateParser.format(date);
      if (endFollowsStart) _endDateController.text = _startDateController.text;
      _focusedDate = date;
      _startDatePickerOpen = false;
    });
  }

  void _selectEndDate(DateTime date) {
    setState(() {
      _endDateController.text = ScheduleDateParser.format(date);
      _focusedDate = date;
      _endDatePickerOpen = false;
    });
  }

  // 시간 휠은 드래그 중 매 프레임 onDateTimeChanged 를 호출하므로, 여기서 피커를
  // 닫으면 슬라이드 도중 피커가 즉시 접히는 버그가 생긴다(값만 반영하고 접지 않음).
  void _selectStartTime(String time) {
    setState(() => _startTimeController.text = time);
  }

  void _selectEndTime(String time) {
    setState(() => _endTimeController.text = time);
  }

  Map<String, dynamic> _payload() {
    String? optional(String value) {
      final trimmed = value.trim();
      return trimmed.isEmpty ? null : trimmed;
    }

    return {
      'title': _titleController.text.trim(),
      'date': _startDateController.text.trim(),
      'end_date': optional(_endDateController.text),
      // 하루 종일이면 시간은 보내지 않는다(서버가 00:00·is_all_day=1 로 저장).
      'start_time': _isAllDay ? null : optional(_startTimeController.text),
      'end_time': _isAllDay ? null : optional(_endTimeController.text),
      'category': _category,
      'priority': _priority,
      'location': optional(_locationController.text),
      'memo': optional(ScheduleModel.stripEndDateToken(_memoController.text)),
      'source': widget.initialSchedule?.source ?? 'user',
      'is_all_day': _isAllDay,
    };
  }

  Future<void> _submit() async {
    final title = _titleController.text.trim();
    final startDate = _startDateController.text.trim();
    final startTime = _startTimeController.text.trim();

    if (title.isEmpty) {
      _showMessage('일정명을 입력해 주세요.');
      return;
    }
    if (startDate.isEmpty) {
      _showMessage('시작 날짜를 입력해 주세요.');
      return;
    }
    if (!_normalizeStartDateInput(showError: true)) return;
    if (_endDateController.text.trim().isNotEmpty &&
        !_normalizeEndDateInput(showError: true)) {
      return;
    }
    if (_endDateController.text.trim().isEmpty) {
      _endDateController.text = _startDateController.text.trim();
    }
    // 하루 종일 일정은 시간 입력/검증을 건너뛴다.
    if (!_isAllDay) {
      if (startTime.isEmpty) {
        _showMessage('시작 시간을 입력해 주세요.');
        return;
      }
      if (_minutesOfDay(startTime) == null) {
        _showMessage('시작 시간은 HH:mm 형식으로 입력해 주세요.');
        return;
      }
      final endTime = _endTimeController.text.trim();
      if (endTime.isNotEmpty && _minutesOfDay(endTime) == null) {
        _showMessage('종료 시간은 HH:mm 형식으로 입력해 주세요.');
        return;
      }
    }
    if (!_isDateOrderValid()) {
      _showMessage(
        _startDateController.text.trim() == _endDateController.text.trim()
            ? '종료 시간은 시작 시간보다 늦어야 합니다.'
            : '종료 날짜는 시작 날짜보다 빠를 수 없습니다.',
      );
      return;
    }

    setState(() => _saving = true);
    try {
      final payload = _payload();
      final ScheduleModel saved;
      if (_isEditMode) {
        saved = await scheduleApi.update(widget.initialSchedule!.id, payload);
      } else {
        saved = await scheduleApi.create(payload);
      }
      triggerDashboardRefresh();
      if (!mounted) return;
      Navigator.pop<ScheduleModel>(context, saved);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      _showMessage('저장 실패: ${e.message}');
    } catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      _showMessage('저장 중 오류: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    final title = _isEditMode ? '일정 수정' : '일정 추가';

    return Container(
      decoration: AppTheme.screenBackground,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          title: Text(title),
          centerTitle: false,
          actions: [
            TextButton(
              onPressed: _saving ? null : () => Navigator.pop(context),
              child: const Text('취소'),
            ),
          ],
        ),
        body: SafeArea(
          top: false,
          child: ListView(
            physics: const BouncingScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 28),
            children: [
              Text(
                _isEditMode ? '기존 일정 정보를 수정합니다.' : '새 일정을 직접 입력합니다.',
                style: AppTextStyles.meta.copyWith(
                  color: AppTheme.textSecondary,
                ),
              ),
              const SizedBox(height: 12),
              ScheduleFormSection(
                children: [
                  ScheduleTextFieldRow(
                    controller: _titleController,
                    label: '일정명',
                    hint: '예: 병원 예약',
                    icon: Icons.title,
                  ),
                  DateTimePickerRow(
                    label: '시작날짜',
                    icon: Icons.event_outlined,
                    dateController: _startDateController,
                    timeController: _startTimeController,
                    dateExpanded: _startDatePickerOpen,
                    timeExpanded: _startTimePickerOpen,
                    focusedDay: _focusedDate,
                    onDateExpandedChanged: (_) => _closePickersExcept('startDate'),
                    onTimeExpandedChanged: (_) => _closePickersExcept('startTime'),
                    onFocusedDayChanged: (date) =>
                        setState(() => _focusedDate = date),
                    onDateSelected: _selectStartDate,
                    onTimeSelected: _selectStartTime,
                    onNormalizeDate: () => _normalizeStartDateInput(),
                    showTime: !_isAllDay,
                  ),
                  DateTimePickerRow(
                    label: '종료날짜',
                    icon: Icons.event_available_outlined,
                    dateController: _endDateController,
                    timeController: _endTimeController,
                    dateExpanded: _endDatePickerOpen,
                    timeExpanded: _endTimePickerOpen,
                    focusedDay: _focusedDate,
                    onDateExpandedChanged: (_) => _closePickersExcept('endDate'),
                    onTimeExpandedChanged: (_) => _closePickersExcept('endTime'),
                    onFocusedDayChanged: (date) =>
                        setState(() => _focusedDate = date),
                    onDateSelected: _selectEndDate,
                    onTimeSelected: _selectEndTime,
                    onNormalizeDate: () => _normalizeEndDateInput(),
                    showTime: !_isAllDay,
                    showDivider: false,
                  ),
                ],
              ),
              ScheduleFormSection(
                children: [
                  ScheduleCategorySelector(
                    value: _category,
                    onChanged: (value) => setState(() => _category = value),
                  ),
                  _PriorityRow(
                    value: _priority,
                    onChanged: (value) => setState(() => _priority = value),
                    showDivider: false,
                  ),
                ],
              ),
              ScheduleFormSection(
                children: [
                  ScheduleTextFieldRow(
                    controller: _locationController,
                    label: '장소',
                    hint: '장소 미정',
                    icon: Icons.place_outlined,
                  ),
                  ScheduleTextFieldRow(
                    controller: _memoController,
                    label: '메모',
                    hint: '메모 입력',
                    icon: Icons.notes_outlined,
                    maxLines: 3,
                    showDivider: false,
                  ),
                ],
              ),
              ScheduleFormSection(
                children: [
                  const ScheduleDisabledOptionRow(
                    icon: Icons.group_outlined,
                    label: '참석자',
                    value: '추후 지원',
                  ),
                  const ScheduleDisabledOptionRow(
                    icon: Icons.notifications_outlined,
                    label: '알림',
                    value: '추후 지원',
                  ),
                  const ScheduleDisabledOptionRow(
                    icon: Icons.repeat,
                    label: '반복',
                    value: '추후 지원',
                  ),
                  ScheduleToggleOptionRow(
                    icon: Icons.wb_sunny_outlined,
                    label: '하루 종일',
                    value: _isAllDay,
                    onChanged: (v) => setState(() => _isAllDay = v),
                    showDivider: false,
                  ),
                ],
              ),
              ScheduleFormSubmitButton(
                saving: _saving,
                label: _isEditMode ? '수정 저장' : '일정 저장',
                onPressed: _submit,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PriorityRow extends StatelessWidget {
  final String value;
  final ValueChanged<String> onChanged;
  final bool showDivider;

  const _PriorityRow({
    required this.value,
    required this.onChanged,
    this.showDivider = true,
  });

  @override
  Widget build(BuildContext context) {
    return ScheduleFormRow(
      icon: Icons.flag_outlined,
      label: '우선순위',
      showDivider: showDivider,
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: value,
          isExpanded: true,
          items: const ['high', 'medium', 'low']
              .map(
                (item) => DropdownMenuItem(
                  value: item,
                  child: Text(_priorityLabel(item)),
                ),
              )
              .toList(),
          onChanged: (next) {
            if (next != null) onChanged(next);
          },
        ),
      ),
    );
  }

  static String _priorityLabel(String value) {
    switch (value) {
      case 'high':
        return '높음';
      case 'low':
        return '낮음';
      default:
        return '보통';
    }
  }
}

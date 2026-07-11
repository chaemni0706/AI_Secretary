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
  final _dateController = TextEditingController();
  final _startTimeController = TextEditingController();
  final _endTimeController = TextEditingController();
  final _locationController = TextEditingController();
  final _memoController = TextEditingController();

  String _category = ScheduleStyles.categoryOrder.last;
  String _priority = 'medium';
  bool _isAllDay = false;
  bool _saving = false;
  bool _datePickerOpen = false;
  bool _startTimePickerOpen = false;
  bool _endTimePickerOpen = false;
  DateTime _focusedDate = DateTime.now();

  bool get _isEditMode => widget.initialSchedule != null;

  @override
  void initState() {
    super.initState();
    final schedule = widget.initialSchedule;
    if (schedule == null) {
      _dateController.text = widget.initialDate ?? '';
      _focusedDate =
          ScheduleDateParser.parse(_dateController.text) ?? DateTime.now();
      return;
    }
    _titleController.text = schedule.title;
    _dateController.text = schedule.date ?? '';
    _startTimeController.text = schedule.startTime ?? '';
    _endTimeController.text = schedule.endTime ?? '';
    _locationController.text = schedule.location ?? '';
    _memoController.text = schedule.memo ?? '';
    _category = ScheduleStyles.categoryLabel(schedule.category);
    _priority = schedule.priority;
    _isAllDay = schedule.isAllDay;
    _focusedDate =
        ScheduleDateParser.parse(_dateController.text) ?? DateTime.now();
  }

  @override
  void dispose() {
    _titleController.dispose();
    _dateController.dispose();
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

  void _closePickersExcept(String target) {
    setState(() {
      _datePickerOpen = target == 'date' ? !_datePickerOpen : false;
      _startTimePickerOpen = target == 'start' ? !_startTimePickerOpen : false;
      _endTimePickerOpen = target == 'end' ? !_endTimePickerOpen : false;
    });
  }

  bool _normalizeDateInput({bool showError = false}) {
    final normalized = ScheduleDateParser.normalize(_dateController.text);
    if (normalized == null) {
      if (showError) _showMessage('날짜 형식을 확인해 주세요.');
      return false;
    }
    _dateController.text = normalized;
    _focusedDate = ScheduleDateParser.parse(normalized) ?? _focusedDate;
    return true;
  }

  void _selectDate(DateTime date) {
    setState(() {
      _dateController.text = ScheduleDateParser.format(date);
      _focusedDate = date;
      _datePickerOpen = false;
    });
  }

  void _selectStartTime(String time) {
    setState(() {
      _startTimeController.text = time;
      _startTimePickerOpen = false;
    });
  }

  void _selectEndTime(String time) {
    setState(() {
      _endTimeController.text = time;
      _endTimePickerOpen = false;
    });
  }

  Map<String, dynamic> _payload() {
    String? optional(String value) {
      final trimmed = value.trim();
      return trimmed.isEmpty ? null : trimmed;
    }

    return {
      'title': _titleController.text.trim(),
      'date': _dateController.text.trim(),
      // 하루 종일이면 시간은 보내지 않는다(서버가 00:00·is_all_day=1 로 저장).
      'start_time': _isAllDay ? null : optional(_startTimeController.text),
      'end_time': _isAllDay ? null : optional(_endTimeController.text),
      'category': _category,
      'priority': _priority,
      'location': optional(_locationController.text),
      'memo': optional(_memoController.text),
      'source': widget.initialSchedule?.source ?? 'user',
      'is_all_day': _isAllDay,
    };
  }

  Future<void> _submit() async {
    final title = _titleController.text.trim();
    final date = _dateController.text.trim();
    final startTime = _startTimeController.text.trim();

    if (title.isEmpty) {
      _showMessage('일정명을 입력해 주세요.');
      return;
    }
    if (date.isEmpty) {
      _showMessage('날짜를 입력해 주세요.');
      return;
    }
    if (!_normalizeDateInput(showError: true)) return;
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
      if (!_isTimeOrderValid()) {
        _showMessage('종료 시간은 시작 시간보다 늦어야 합니다.');
        return;
      }
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
                  ScheduleDatePickerRow(
                    controller: _dateController,
                    expanded: _datePickerOpen,
                    focusedDay: _focusedDate,
                    onExpandedChanged: (_) => _closePickersExcept('date'),
                    onFocusedDayChanged: (date) =>
                        setState(() => _focusedDate = date),
                    onDateSelected: _selectDate,
                    onNormalize: () => _normalizeDateInput(),
                  ),
                  // 하루 종일이면 시작/종료 시간 선택을 숨긴다.
                  if (!_isAllDay) ...[
                    ScheduleTimePickerRow(
                      controller: _startTimeController,
                      label: '시작',
                      icon: Icons.schedule_outlined,
                      expanded: _startTimePickerOpen,
                      onExpandedChanged: (_) => _closePickersExcept('start'),
                      onTimeSelected: _selectStartTime,
                    ),
                    ScheduleTimePickerRow(
                      controller: _endTimeController,
                      label: '종료',
                      icon: Icons.schedule_send_outlined,
                      expanded: _endTimePickerOpen,
                      onExpandedChanged: (_) => _closePickersExcept('end'),
                      onTimeSelected: _selectEndTime,
                      showDivider: false,
                    ),
                  ],
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

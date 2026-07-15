import 'package:flutter/material.dart';
import '../models/schedule_model.dart';
import '../services/api_client.dart';
import '../services/schedule_api.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import '../widgets/picker_field.dart';

/// 일정 수정 화면.
///
/// 기존 [ScheduleModel] 을 받아 제목/날짜/기간/시간/장소/메모를 수정하고
/// `PATCH /local/schedules/{id}` 로 저장한다. 저장 성공 시 수정된
/// [ScheduleModel] 을 `Navigator.pop` 결과로 돌려주며, 호출부(상세 화면)는
/// 이를 받아 화면을 갱신하고 캘린더 새로고침을 트리거한다.
///
/// 기간 일정(종료일)은 백엔드 스키마를 바꾸지 않기 위해, 기존 캘린더가 이미
/// 인식하는 memo 의 `end_date: YYYY-MM-DD` 규칙으로 저장한다.
class ScheduleEditScreen extends StatefulWidget {
  final ScheduleModel schedule;

  const ScheduleEditScreen({super.key, required this.schedule});

  @override
  State<ScheduleEditScreen> createState() => _ScheduleEditScreenState();
}

class _ScheduleEditScreenState extends State<ScheduleEditScreen> {
  late final TextEditingController _titleController;
  late final TextEditingController _locationController;
  late final TextEditingController _memoController;

  String? _date; // YYYY-MM-DD
  String? _endDate; // YYYY-MM-DD (기간 일정, 선택)
  String? _startTime; // HH:mm
  String? _endTime; // HH:mm

  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final s = widget.schedule;
    _titleController = TextEditingController(text: s.title);
    _locationController = TextEditingController(text: s.location ?? '');
    // memo 는 기계용 end_date 토큰을 제외한 순수 메모만 편집한다.
    _memoController = TextEditingController(
      text: ScheduleModel.stripEndDateToken(s.memo),
    );
    _date = s.date;
    _endDate = s.effectiveEndDate;
    _startTime = s.startTime;
    _endTime = s.endTime;
  }

  @override
  void dispose() {
    _titleController.dispose();
    _locationController.dispose();
    _memoController.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final picked = await DateTimePickers.pickDate(context, initial: _date);
    if (picked == null) return;
    setState(() {
      _date = picked;
      // 시작일이 종료일보다 뒤로 가면 종료일을 초기화한다.
      if (_endDate != null && _endDate!.compareTo(picked) < 0) _endDate = null;
    });
  }

  Future<void> _pickEndDate() async {
    final picked = await DateTimePickers.pickDate(
      context,
      initial: _endDate ?? _date,
      // 종료일은 시작일 이후만 선택 가능.
      firstDate: DateTimePickers.parseDate(_date),
    );
    if (picked == null) return;
    setState(() => _endDate = picked);
  }

  Future<void> _pickStartTime() async {
    final picked = await DateTimePickers.pickTime(context, initial: _startTime);
    if (picked == null) return;
    setState(() => _startTime = picked);
  }

  Future<void> _pickEndTime() async {
    final picked = await DateTimePickers.pickTime(context, initial: _endTime);
    if (picked == null) return;
    setState(() => _endTime = picked);
  }

  Future<void> _save() async {
    final title = _titleController.text.trim();
    if (title.isEmpty) {
      _snack('제목을 입력해 주세요.');
      return;
    }
    if (_date == null || _date!.isEmpty) {
      _snack('날짜를 선택해 주세요.');
      return;
    }
    // 기간 유효성: 종료일은 시작일 이후여야 한다.
    if (_endDate != null && _endDate!.compareTo(_date!) < 0) {
      _snack('종료일은 시작일과 같거나 이후여야 해요.');
      return;
    }
    // 시간 유효성: 종료 시간이 있으면 시작 시간보다 뒤여야 한다(같은 날 기준).
    if (_startTime != null &&
        _endTime != null &&
        _endTime!.compareTo(_startTime!) <= 0) {
      _snack('종료 시간은 시작 시간보다 뒤여야 해요.');
      return;
    }

    setState(() => _saving = true);

    // 기간 종료일은 memo 의 end_date 토큰으로 저장(백엔드 스키마 불변).
    final memo = ScheduleModel.encodeMemoWithEndDate(
      _memoController.text,
      _endDate,
    );

    final payload = <String, dynamic>{
      'title': title,
      'date': _date,
      'start_time': _startTime,
      'end_time': _endTime,
      'location': _locationController.text.trim(),
      'memo': memo ?? '',
    };

    try {
      final updated = await scheduleApi.update(widget.schedule.id, payload);
      if (!mounted) return;
      Navigator.pop<ScheduleModel>(context, updated);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      _snack('수정 실패: ${e.message}');
    } catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      _snack('수정 중 오류: $e');
    }
  }

  void _snack(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          title: const Text('일정 수정'),
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
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
            children: [
              GlassCard(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    _TextInput(
                      controller: _titleController,
                      label: '제목',
                      icon: Icons.title,
                    ),
                    PickerField(
                      icon: Icons.event_outlined,
                      label: '시작 날짜',
                      value: _date,
                      hint: '날짜 선택',
                      onTap: _pickDate,
                    ),
                    PickerField(
                      icon: Icons.event_repeat_outlined,
                      label: '종료 날짜 (기간 일정, 선택)',
                      value: _endDate,
                      hint: '하루 일정',
                      onTap: _pickEndDate,
                      onClear: () => setState(() => _endDate = null),
                    ),
                    PickerField(
                      icon: Icons.schedule_outlined,
                      label: '시작 시간 (선택)',
                      value: _startTime,
                      hint: '시간 선택',
                      onTap: _pickStartTime,
                      onClear: () => setState(() => _startTime = null),
                    ),
                    PickerField(
                      icon: Icons.schedule,
                      label: '종료 시간 (선택)',
                      value: _endTime,
                      hint: '시간 선택',
                      onTap: _pickEndTime,
                      onClear: () => setState(() => _endTime = null),
                    ),
                    _TextInput(
                      controller: _locationController,
                      label: '장소',
                      icon: Icons.place_outlined,
                    ),
                    _TextInput(
                      controller: _memoController,
                      label: '메모',
                      icon: Icons.notes_outlined,
                      maxLines: 3,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: _saving ? null : () => Navigator.pop(context),
                      child: const Text('취소'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: FilledButton(
                      onPressed: _saving ? null : _save,
                      style: FilledButton.styleFrom(
                        backgroundColor: AppTheme.blue,
                        foregroundColor: Colors.white,
                      ),
                      child: _saving
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : const Text('저장'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TextInput extends StatelessWidget {
  final TextEditingController controller;
  final String label;
  final IconData icon;
  final int maxLines;

  const _TextInput({
    required this.controller,
    required this.label,
    required this.icon,
    this.maxLines = 1,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextField(
        controller: controller,
        maxLines: maxLines,
        decoration: InputDecoration(
          labelText: label,
          prefixIcon: Icon(icon, size: 20),
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
      ),
    );
  }
}

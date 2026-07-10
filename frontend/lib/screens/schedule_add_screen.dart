import 'package:flutter/material.dart';
import '../models/schedule_model.dart';
import '../services/api_client.dart';
import '../services/schedule_api.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../theme/schedule_styles.dart';
import '../widgets/glass_card.dart';
import '../widgets/picker_field.dart';

/// 수동 일정 추가 화면(폼). 캘린더에서 "+ 일정 추가"로 진입하며 선택 날짜가
/// 미리 채워진다. 저장은 기존 `POST /local/schedules/from-draft`(createFromDraft)를
/// 재사용하고, 성공 시 [ScheduleModel] 을 pop 결과로 돌려준다.
class ScheduleAddScreen extends StatefulWidget {
  /// 미리 채울 시작 날짜("YYYY-MM-DD"). 없으면 오늘.
  final String? initialDate;

  const ScheduleAddScreen({super.key, this.initialDate});

  @override
  State<ScheduleAddScreen> createState() => _ScheduleAddScreenState();
}

class _ScheduleAddScreenState extends State<ScheduleAddScreen> {
  final _titleController = TextEditingController();
  final _locationController = TextEditingController();
  final _memoController = TextEditingController();

  String? _date;
  String? _endDate;
  String? _startTime;
  String? _endTime;
  String _category = ScheduleStyles.categoryOrder.first;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _date = widget.initialDate ?? DateTimePickers.formatDate(DateTime.now());
  }

  @override
  void dispose() {
    _titleController.dispose();
    _locationController.dispose();
    _memoController.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final p = await DateTimePickers.pickDate(context, initial: _date);
    if (p == null) return;
    setState(() {
      _date = p;
      if (_endDate != null && _endDate!.compareTo(p) < 0) _endDate = null;
    });
  }

  Future<void> _pickEndDate() async {
    final p = await DateTimePickers.pickDate(
      context,
      initial: _endDate ?? _date,
      firstDate: DateTimePickers.parseDate(_date),
    );
    if (p == null) return;
    setState(() => _endDate = p);
  }

  Future<void> _pickStart() async {
    final p = await DateTimePickers.pickTime(context, initial: _startTime);
    if (p == null) return;
    setState(() => _startTime = p);
  }

  Future<void> _pickEnd() async {
    final p = await DateTimePickers.pickTime(context, initial: _endTime);
    if (p == null) return;
    setState(() => _endTime = p);
  }

  Future<void> _save() async {
    final title = _titleController.text.trim();
    if (title.isEmpty) return _snack('제목을 입력해 주세요.');
    if (_date == null) return _snack('날짜를 선택해 주세요.');
    if (_startTime == null) return _snack('시작 시간을 선택해 주세요.');
    if (_endDate != null && _endDate!.compareTo(_date!) < 0) {
      return _snack('종료일은 시작일과 같거나 이후여야 해요.');
    }
    if (_endTime != null && _endTime!.compareTo(_startTime!) <= 0) {
      return _snack('종료 시간은 시작 시간보다 뒤여야 해요.');
    }

    setState(() => _saving = true);
    // memo는 순수 사용자 메모만 전달하고, end_date는 별도 필드로 넘긴다.
    // (ScheduleDraftMapper가 end_date를 memo의 'end_date:' 규칙으로 1회만 인코딩)
    final draft = <String, dynamic>{
      'title': title,
      'date': _date,
      'end_date': _endDate,
      'start_time': _startTime,
      'end_time': _endTime,
      'location': _locationController.text.trim(),
      'memo': _memoController.text.trim(),
      'category': _category,
      'priority': 'medium',
      'source': 'user',
    };
    try {
      final saved = await scheduleApi.createFromDraft(
        draft,
        intent: 'create_schedule',
      );
      if (!mounted) return;
      Navigator.pop<ScheduleModel>(context, saved);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      _snack('저장 실패: ${e.message}');
    } catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      _snack('저장 중 오류: $e');
    }
  }

  void _snack(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          title: const Text('일정 추가'),
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
                      label: '시작 시간',
                      value: _startTime,
                      hint: '시간 선택',
                      onTap: _pickStart,
                    ),
                    PickerField(
                      icon: Icons.schedule,
                      label: '종료 시간 (선택)',
                      value: _endTime,
                      hint: '시간 선택',
                      onTap: _pickEnd,
                      onClear: () => setState(() => _endTime = null),
                    ),
                    _CategoryDropdown(
                      value: _category,
                      onChanged: (v) => setState(() => _category = v),
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

class _CategoryDropdown extends StatelessWidget {
  final String value;
  final ValueChanged<String> onChanged;

  const _CategoryDropdown({required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: DropdownButtonFormField<String>(
        initialValue: value,
        items: ScheduleStyles.categoryOrder
            .map((c) => DropdownMenuItem(value: c, child: Text(c)))
            .toList(),
        onChanged: (v) => onChanged(v ?? value),
        decoration: InputDecoration(
          labelText: '카테고리',
          prefixIcon: const Icon(Icons.category_outlined, size: 20),
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

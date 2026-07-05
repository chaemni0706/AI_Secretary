import 'package:flutter/material.dart';
import '../models/todo_model.dart';
import '../services/api_client.dart';
import '../services/todo_api.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../theme/todo_styles.dart';
import '../widgets/glass_card.dart';

class TodoAddScreen extends StatefulWidget {
  const TodoAddScreen({super.key});

  @override
  State<TodoAddScreen> createState() => _TodoAddScreenState();
}

class _TodoAddScreenState extends State<TodoAddScreen> {
  final TextEditingController _titleController = TextEditingController();
  final TextEditingController _dateController = TextEditingController();
  final TextEditingController _timeController = TextEditingController();
  final TextEditingController _memoController = TextEditingController();

  String _category = TodoStyles.categoryOrder.first;
  Color _categoryColor = TodoStyles.categoryColor(
    TodoStyles.categoryOrder.first,
  );
  String _priority = 'medium';
  bool _repeat = false;
  bool _notify = true;
  bool _saving = false;

  static const _palette = [
    AppTheme.blue,
    AppTheme.orange,
    AppTheme.purple,
    AppTheme.green,
    AppTheme.teal,
    AppTheme.red,
  ];

  @override
  void dispose() {
    _titleController.dispose();
    _dateController.dispose();
    _timeController.dispose();
    _memoController.dispose();
    super.dispose();
  }

  String _colorHex(Color color) {
    final value = color.toARGB32() & 0x00ffffff;
    return '#${value.toRadixString(16).padLeft(6, '0').toUpperCase()}';
  }

  String? _buildMemo() {
    final parts = <String>[];
    final memo = _memoController.text.trim();
    if (memo.isNotEmpty) parts.add(memo);

    final time = _timeController.text.trim();
    if (time.isNotEmpty) parts.add('시간: $time');
    parts.add('카테고리 색상: ${_colorHex(_categoryColor)}');
    parts.add('반복 여부: ${_repeat ? '예' : '아니오'}');
    parts.add('알림 여부: ${_notify ? '예' : '아니오'}');

    return parts.isEmpty ? null : parts.join('\n');
  }

  Future<void> _saveTodo() async {
    final title = _titleController.text.trim();
    if (title.isEmpty) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('제목을 입력해 주세요.')));
      return;
    }

    setState(() => _saving = true);
    try {
      final saved = await todoApi.create({
        'title': title,
        'due_date': _dateController.text.trim().isEmpty
            ? null
            : _dateController.text.trim(),
        'priority': _priority,
        'completed': false,
        'category': _category,
        'memo': _buildMemo(),
        'source': 'user',
      });
      if (!mounted) return;
      Navigator.pop<TodoModel>(context, saved);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('저장 실패: ${e.message}')));
    } catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('저장 중 오류: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          title: const Text('할 일 추가'),
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
                    _InputField(
                      controller: _titleController,
                      label: '제목',
                      icon: Icons.title,
                    ),
                    _InputField(
                      controller: _dateController,
                      label: '날짜',
                      hint: 'YYYY-MM-DD',
                      icon: Icons.event_outlined,
                    ),
                    _InputField(
                      controller: _timeController,
                      label: '시간',
                      hint: 'HH:mm',
                      icon: Icons.schedule_outlined,
                    ),
                    _DropdownField<String>(
                      label: '카테고리',
                      icon: Icons.category_outlined,
                      value: _category,
                      items: TodoStyles.categoryOrder,
                      labelBuilder: (value) => value,
                      onChanged: (value) {
                        if (value == null) return;
                        setState(() {
                          _category = value;
                          _categoryColor = TodoStyles.categoryColor(value);
                        });
                      },
                    ),
                    _ColorSelector(
                      selected: _categoryColor,
                      colors: _palette,
                      onChanged: (color) => setState(() {
                        _categoryColor = color;
                      }),
                    ),
                    _InputField(
                      controller: _memoController,
                      label: '메모',
                      icon: Icons.notes_outlined,
                      maxLines: 3,
                    ),
                    SwitchListTile.adaptive(
                      contentPadding: EdgeInsets.zero,
                      value: _repeat,
                      onChanged: (value) => setState(() => _repeat = value),
                      title: const Text('반복 여부'),
                      secondary: const Icon(Icons.repeat),
                    ),
                    SwitchListTile.adaptive(
                      contentPadding: EdgeInsets.zero,
                      value: _notify,
                      onChanged: (value) => setState(() => _notify = value),
                      title: const Text('알림 여부'),
                      secondary: const Icon(Icons.notifications_outlined),
                    ),
                    _DropdownField<String>(
                      label: '우선순위',
                      icon: Icons.flag_outlined,
                      value: _priority,
                      items: const ['high', 'medium', 'low'],
                      labelBuilder: TodoStyles.priorityLabel,
                      onChanged: (value) {
                        if (value == null) return;
                        setState(() => _priority = value);
                      },
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
                      onPressed: _saving ? null : _saveTodo,
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

class _InputField extends StatelessWidget {
  final TextEditingController controller;
  final String label;
  final String? hint;
  final IconData icon;
  final int maxLines;

  const _InputField({
    required this.controller,
    required this.label,
    required this.icon,
    this.hint,
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
          hintText: hint,
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

class _DropdownField<T> extends StatelessWidget {
  final String label;
  final IconData icon;
  final T value;
  final List<T> items;
  final String Function(T value) labelBuilder;
  final ValueChanged<T?> onChanged;

  const _DropdownField({
    required this.label,
    required this.icon,
    required this.value,
    required this.items,
    required this.labelBuilder,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: DropdownButtonFormField<T>(
        initialValue: value,
        items: items
            .map(
              (item) => DropdownMenuItem<T>(
                value: item,
                child: Text(labelBuilder(item)),
              ),
            )
            .toList(),
        onChanged: onChanged,
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

class _ColorSelector extends StatelessWidget {
  final Color selected;
  final List<Color> colors;
  final ValueChanged<Color> onChanged;

  const _ColorSelector({
    required this.selected,
    required this.colors,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        children: [
          const SizedBox(
            width: 48,
            child: Icon(Icons.palette_outlined, color: AppTheme.textSecondary),
          ),
          Expanded(
            child: Wrap(
              spacing: 10,
              children: colors
                  .map(
                    (color) => GestureDetector(
                      onTap: () => onChanged(color),
                      child: Container(
                        width: 30,
                        height: 30,
                        decoration: BoxDecoration(
                          color: color,
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: selected == color
                                ? AppTheme.textPrimary
                                : Colors.white,
                            width: selected == color ? 2 : 1,
                          ),
                        ),
                      ),
                    ),
                  )
                  .toList(),
            ),
          ),
        ],
      ),
    );
  }
}

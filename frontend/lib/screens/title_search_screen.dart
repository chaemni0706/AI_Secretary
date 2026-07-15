import 'package:flutter/material.dart';
import '../theme/app_constants.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';

/// 제목으로 검색하는 공용 화면 — 일정 검색/할 일 검색 양쪽에서 재사용한다.
///
/// [items] 는 호출한 화면이 이미 불러와 둔 목록을 그대로 받는다(새 네트워크
/// 호출도, mock 데이터도 없음). [titleOf] 로 검색 대상 문자열을 뽑고,
/// [itemBuilder] 로 각 결과를 렌더링한다(호출한 화면이 이미 쓰는
/// ScheduleCard/TodoCard 를 그대로 넘겨받아 재사용).
class TitleSearchScreen<T> extends StatefulWidget {
  final String title;
  final String hintText;
  final List<T> items;
  final String Function(T item) titleOf;
  final Widget Function(BuildContext context, T item) itemBuilder;

  const TitleSearchScreen({
    super.key,
    required this.title,
    required this.hintText,
    required this.items,
    required this.titleOf,
    required this.itemBuilder,
  });

  @override
  State<TitleSearchScreen<T>> createState() => _TitleSearchScreenState<T>();
}

class _TitleSearchScreenState<T> extends State<TitleSearchScreen<T>> {
  final _controller = TextEditingController();
  String _query = '';

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  List<T> get _filtered {
    final query = _query.trim().toLowerCase();
    if (query.isEmpty) return const [];
    return widget.items
        .where((item) => widget.titleOf(item).toLowerCase().contains(query))
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    final hasQuery = _query.trim().isNotEmpty;
    final results = _filtered;

    return Container(
      decoration: AppTheme.screenBackground,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(title: Text(widget.title), centerTitle: false),
        body: SafeArea(
          top: false,
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
                child: GlassCard(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 14,
                    vertical: 2,
                  ),
                  child: TextField(
                    controller: _controller,
                    autofocus: true,
                    onChanged: (value) => setState(() => _query = value),
                    style: AppTextStyles.cardTitle.copyWith(
                      color: AppTheme.textPrimary,
                    ),
                    decoration: InputDecoration(
                      isDense: true,
                      border: InputBorder.none,
                      icon: Icon(
                        Icons.search,
                        color: AppTheme.textSecondary,
                        size: 20,
                      ),
                      hintText: widget.hintText,
                      hintStyle: AppTextStyles.cardTitle.copyWith(
                        color: AppTheme.textSecondary.withValues(alpha: 0.7),
                      ),
                    ),
                  ),
                ),
              ),
              Expanded(
                child: !hasQuery
                    ? const _SearchEmptyState(message: '검색어를 입력해 주세요.')
                    : results.isEmpty
                    ? const _SearchEmptyState(message: '검색 결과가 없습니다.')
                    : ListView.builder(
                        padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                        itemCount: results.length,
                        itemBuilder: (context, index) =>
                            widget.itemBuilder(context, results[index]),
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SearchEmptyState extends StatelessWidget {
  final String message;

  const _SearchEmptyState({required this.message});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Text(
        message,
        style: AppTextStyles.meta.copyWith(color: AppTheme.textSecondary),
      ),
    );
  }
}

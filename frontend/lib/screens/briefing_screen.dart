import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import '../models/briefing_model.dart';
import '../services/briefing_api.dart';
import '../services/api_client.dart';

class BriefingScreen extends StatefulWidget {
  const BriefingScreen({super.key});

  @override
  State<BriefingScreen> createState() => _BriefingScreenState();
}

class _BriefingScreenState extends State<BriefingScreen> {
  bool _loading = true;
  String? _error;
  BriefingModel? _data;

  @override
  void initState() {
    super.initState();
    _loadBriefing();
  }

  Future<void> _loadBriefing() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      // 내부적으로 GET /dashboard/today → POST /briefings/daily 순으로 호출.
      final b = await briefingApi.getDailyBriefing();
      if (!mounted) return;
      setState(() {
        _data = b;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = '브리핑을 불러오지 못했습니다. ($e)';
        _loading = false;
      });
    }
  }

  static const _weekKo = ['', '월', '화', '수', '목', '금', '토', '일'];
  String _todayLabel() {
    final n = DateTime.now();
    return '${n.month}월 ${n.day}일 ${_weekKo[n.weekday]}요일';
  }

  String _prioKo(String p) =>
      p == 'high' ? '높음' : (p == 'low' ? '낮음' : '보통');
  Color _prioColor(String p) =>
      p == 'high' ? AppTheme.red : (p == 'low' ? AppTheme.textSecondary : AppTheme.orange);

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppTheme.screenBackground,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          leading: GestureDetector(
            onTap: () => Navigator.pop(context),
            child: Container(
              margin: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.7),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.chevron_left,
                  color: AppTheme.textPrimary, size: 26),
            ),
          ),
          title: const Text('오늘의 브리핑'),
          actions: [
            IconButton(
              onPressed: _loading ? null : _loadBriefing,
              icon: const Icon(Icons.refresh, color: AppTheme.textPrimary),
            ),
          ],
        ),
        body: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? _buildError()
                : _buildContent(),
      ),
    );
  }

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: GlassCard(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off,
                  color: AppTheme.textSecondary, size: 34),
              const SizedBox(height: 10),
              Text(
                _error ?? '브리핑을 불러오지 못했습니다.',
                textAlign: TextAlign.center,
                style: const TextStyle(
                    fontSize: 14, color: AppTheme.textPrimary),
              ),
              const SizedBox(height: 4),
              const Text(
                '백엔드 서버가 실행 중인지 확인하세요.',
                textAlign: TextAlign.center,
                style:
                    TextStyle(fontSize: 12, color: AppTheme.textSecondary),
              ),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: _loadBriefing,
                style:
                    FilledButton.styleFrom(backgroundColor: AppTheme.blue),
                child: const Text('다시 시도'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildContent() {
    final data = _data!;
    return RefreshIndicator(
      onRefresh: _loadBriefing,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(
          parent: BouncingScrollPhysics(),
        ),
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 80),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildDateBadge(),
            const SizedBox(height: 16),
            _buildSummaryCard(data),
            const SizedBox(height: 16),
            if (data.keyPoints.isNotEmpty) ...[
              _buildKeyPoints(data),
              const SizedBox(height: 16),
            ],
            if (data.priorityOrder.isNotEmpty) _buildPriorityOrder(data),
          ],
        ),
      ),
    );
  }

  Widget _buildDateBadge() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: AppTheme.blue.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.blue.withOpacity(0.2)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.auto_awesome, color: AppTheme.blue, size: 16),
          const SizedBox(width: 6),
          Text(
            _todayLabel(),
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: AppTheme.blue,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSummaryCard(BriefingModel data) {
    final summary =
        data.summary.isNotEmpty ? data.summary : '오늘은 등록된 일정이 없습니다.';
    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.auto_awesome, color: AppTheme.purple, size: 18),
              SizedBox(width: 8),
              Text(
                '요약',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            summary,
            style: const TextStyle(
              fontSize: 14,
              color: AppTheme.textPrimary,
              height: 1.55,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildKeyPoints(BriefingModel data) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionHeader(title: '핵심 포인트'),
        GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (var i = 0; i < data.keyPoints.length; i++) ...[
                if (i > 0) const SizedBox(height: 10),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Padding(
                      padding: EdgeInsets.only(top: 2),
                      child: Icon(Icons.check_circle_outline,
                          color: AppTheme.green, size: 16),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        data.keyPoints[i],
                        style: const TextStyle(
                          fontSize: 14,
                          color: AppTheme.textPrimary,
                          height: 1.45,
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildPriorityOrder(BriefingModel data) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionHeader(title: '우선순위'),
        ...data.priorityOrder.map((item) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: GlassCard(
                padding: const EdgeInsets.all(14),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(
                        color: _prioColor(item.priority).withOpacity(0.12),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(Icons.flag_outlined,
                          color: _prioColor(item.priority), size: 20),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Flexible(
                                child: Text(
                                  item.title,
                                  style: const TextStyle(
                                    fontSize: 14,
                                    fontWeight: FontWeight.w600,
                                    color: AppTheme.textPrimary,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 8),
                              PillBadge(
                                label: _prioKo(item.priority),
                                color: _prioColor(item.priority),
                              ),
                            ],
                          ),
                          if (item.reason.isNotEmpty) ...[
                            const SizedBox(height: 3),
                            Text(
                              item.reason,
                              style: const TextStyle(
                                fontSize: 12,
                                color: AppTheme.textSecondary,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            )),
      ],
    );
  }
}

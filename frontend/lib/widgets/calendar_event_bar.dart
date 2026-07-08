import 'package:flutter/material.dart';
import '../theme/app_constants.dart';

class CalendarEventBar extends StatelessWidget {
  final String title;
  final Color color;
  final bool startsOnThisDay;
  final bool endsOnThisDay;

  const CalendarEventBar({
    super.key,
    required this.title,
    required this.color,
    this.startsOnThisDay = true,
    this.endsOnThisDay = true,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 14,
      margin: const EdgeInsets.only(top: 1),
      padding: EdgeInsets.only(
        left: startsOnThisDay ? 5 : 2,
        right: endsOnThisDay ? 5 : 2,
      ),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.82),
        borderRadius: BorderRadius.horizontal(
          left: Radius.circular(startsOnThisDay ? AppRadii.small : 1),
          right: Radius.circular(endsOnThisDay ? AppRadii.small : 1),
        ),
      ),
      alignment: Alignment.centerLeft,
      child: startsOnThisDay
          ? Text(
              title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              textScaler: TextScaler.noScaling,
              style: const TextStyle(
                fontSize: 9,
                fontWeight: FontWeight.w700,
                color: Colors.white,
                height: 1,
              ),
            )
          : const SizedBox.shrink(),
    );
  }
}

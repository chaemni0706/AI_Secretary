/// 약봉투 OCR 분석 및 복약 루틴 API 응답(`data`) 파싱 모델.
///
/// 백엔드 공통 envelope `{success, message, data}` 에서 `data` 부분만 담는다.
/// 필드명은 backend/routers/medicine.py, routines.py 의 응답과 1:1 대응한다.
library;

/// `POST /api/v1/medicine/analyze` 로 인식된 약 1건.
///
/// 약품명 행을 기준으로 함량/1회 복용량/횟수/기간을 하나로 묶은 결과다.
/// (OCR 신뢰도/불확실 표시는 이 화면에서 다루지 않으므로 필드 자체가 없다.)
class MedicineItem {
  final String medicineName;
  final String dose;
  final int? frequencyPerDay;
  final int? durationDays;

  const MedicineItem({
    required this.medicineName,
    required this.dose,
    this.frequencyPerDay,
    this.durationDays,
  });

  factory MedicineItem.fromJson(Map<String, dynamic> json) {
    return MedicineItem(
      medicineName: (json['medicine_name'] ?? '').toString(),
      dose: (json['dose'] ?? '').toString(),
      frequencyPerDay: json['frequency_per_day'] as int?,
      durationDays: json['duration_days'] as int?,
    );
  }

  /// `POST /api/v1/routines/medicine` 요청 바디의 `medicines[]` 항목 형식.
  Map<String, dynamic> toRoutineRequestJson() => {
    'medicine_name': medicineName,
    'dose': dose,
    'frequency_per_day': frequencyPerDay,
    'duration_days': durationDays,
  };
}

/// `POST /api/v1/medicine/analyze` 의 `data` 전체.
class MedicineAnalysisResult {
  final String sourceType;
  final String recordType;
  final String imageFile;
  final String? dispensedDate;
  final String dispensedDateNote;
  final List<MedicineItem> medicines;
  final String status;
  final bool needsUserConfirmation;
  final String warning;

  const MedicineAnalysisResult({
    required this.sourceType,
    required this.recordType,
    required this.imageFile,
    required this.dispensedDate,
    required this.dispensedDateNote,
    required this.medicines,
    required this.status,
    required this.needsUserConfirmation,
    required this.warning,
  });

  factory MedicineAnalysisResult.fromJson(Map<String, dynamic> json) {
    final rawMedicines = json['medicines'];
    final dispensedDate = json['dispensed_date'];
    return MedicineAnalysisResult(
      sourceType: (json['source_type'] ?? '').toString(),
      recordType: (json['record_type'] ?? '').toString(),
      imageFile: (json['image_file'] ?? '').toString(),
      dispensedDate: dispensedDate?.toString(),
      dispensedDateNote: (json['dispensed_date_note'] ?? '').toString(),
      medicines: rawMedicines is List
          ? rawMedicines
                .map((e) => MedicineItem.fromJson(Map<String, dynamic>.from(e as Map)))
                .toList()
          : const [],
      status: (json['status'] ?? '').toString(),
      needsUserConfirmation: json['needs_user_confirmation'] == true,
      warning: (json['warning'] ?? '').toString(),
    );
  }
}

/// `POST`/`GET /api/v1/routines/medicine` 의 루틴 1건 (약 단위 요약).
class MedicineRoutine {
  final String routineId;
  final String medicineName;
  final String doseText;
  final String startDate;
  final String endDate;
  final int durationDays;
  final List<String> times;
  final String status;

  const MedicineRoutine({
    required this.routineId,
    required this.medicineName,
    required this.doseText,
    required this.startDate,
    required this.endDate,
    required this.durationDays,
    required this.times,
    required this.status,
  });

  factory MedicineRoutine.fromJson(Map<String, dynamic> json) {
    final rawTimes = json['times'];
    return MedicineRoutine(
      routineId: (json['routine_id'] ?? '').toString(),
      medicineName: (json['medicine_name'] ?? '').toString(),
      doseText: (json['dose_text'] ?? '').toString(),
      startDate: (json['start_date'] ?? '').toString(),
      endDate: (json['end_date'] ?? '').toString(),
      durationDays: (json['duration_days'] as num?)?.toInt() ?? 0,
      times: rawTimes is List ? rawTimes.map((e) => e.toString()).toList() : const [],
      status: (json['status'] ?? '').toString(),
    );
  }
}

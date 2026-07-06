class UserProfileMock {
  final String name;
  final String greeting;
  final String personality;
  final String job;
  final String age;
  final String gender;
  final String lifePattern;
  final String notificationPreference;
  final List<String> interests;
  final String assistantTone;

  const UserProfileMock({
    required this.name,
    required this.greeting,
    required this.personality,
    required this.job,
    required this.age,
    required this.gender,
    required this.lifePattern,
    required this.notificationPreference,
    required this.interests,
    required this.assistantTone,
  });
}

const mockUserProfile = UserProfileMock(
  name: '사용자',
  greeting: '오늘도 일정과 할 일을 차분히 정리해볼까요?',
  personality: '계획형',
  job: '직장인',
  age: '29',
  gender: '미입력',
  lifePattern: '아침 집중형',
  notificationPreference: '중요 알림 위주',
  interests: ['일정', '건강', '가계부'],
  assistantTone: '사려 깊은',
);

# AI 어시스턴트 다국어 응답 + 4대 연구 페이지 네비게이션 연동

- **ID**: 002
- **날짜**: 2026-02-27
- **유형**: 기능 추가

## 작업 요약
AI 어시스턴트 챗봇에 다국어 응답(영어/한국어 자동 감지) 기능과 4대 연구 기능 페이지 네비게이션 연동을 구현. 사용자 질문에 따라 해당 도메인(주제 발굴/공정 예측/진단 분석/이론 연구) 페이지로 이동하는 버튼을 챗봇 내에 표시하고, 페이지 이동 시 쿼리 파라미터를 통해 자동 탭 전환 및 검색 실행.

## 변경 파일 목록

### System Prompt 강화
- `src/model/struct/agent.py`: CRITICAL Language Rule 섹션 추가 (사용자 언어 감지 → 동일 언어 응답), Page Navigation 가이드 섹션 추가 (navigate_to_page 도구 사용 안내)

### 신규 도구
- `src/model/struct/agent/tools/navigate_to_page.py` (신규): 4대 페이지별 URL/탭/쿼리 파라미터 구성, PAGE_CONFIG 매핑, 탭 유효성 검증

### AI 어시스턴트 UI
- `src/app/page.agent/view.ts`: navigations[] 배열 추가, handleChatEvent에서 navigate_to_page 결과 파싱, navigateToPage() 메서드, getPageConfig() 페이지 아이콘/색상 매핑
- `src/app/page.agent/view.pug`: 네비게이션 카드 UI (아이콘, 한/영 제목, 검색어, 화살표 버튼), navigate_to_page 도구 호출/결과 숨김 처리

### 4대 페이지 쿼리 파라미터 지원
- `src/app/page.research/view.ts`: ActivatedRoute 주입, handleQueryParams() — tab/q/gapKeywords/hypothesisCondition 파라미터 → 자동 탭 전환 및 검색
- `src/app/page.prediction/view.ts`: ActivatedRoute 주입, handleQueryParams() — tab/q/process_type/gas_type/pressure/power/temperature/substrate/target_property/inverseTarget/analysisParam 파라미터
- `src/app/page.diagnosis/view.ts`: ActivatedRoute 주입, handleQueryParams() — tab/q/diagType/symptom/methodA/methodB 파라미터
- `src/app/page.theory/view.ts`: ActivatedRoute 주입, handleQueryParams() — tab/q/equationQuery/graphSearchQuery 파라미터

## 핵심 구현 패턴

### navigate_to_page 도구 결과 → 프론트엔드 네비게이션
```
Agent (tool_result) → JSON {action:"navigate", url:"/research?tab=discover&q=plasma"} 
  → view.ts handleChatEvent → msg.navigations[] push
  → view.pug 네비게이션 카드 렌더링
  → 클릭 → service.href(url) → 페이지 이동
  → 페이지 ngOnInit → ActivatedRoute.queryParams → handleQueryParams → 자동 검색
```

### 다국어 응답 규칙
- System Prompt에 "CRITICAL: Language Rule" 섹션 추가
- 사용자 메시지 언어 감지 → 동일 언어로 응답
- 한국어 질문 → 한국어 답변, 영어 질문 → 영어 답변

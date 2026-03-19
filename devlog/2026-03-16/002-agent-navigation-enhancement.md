# AI Agent 키워드 분류 → 페이지 네비게이션 자동 실행 강화

- **ID**: 002
- **날짜**: 2026-03-16
- **유형**: 기능 추가 / 버그 수정

## 작업 요약
AI Agent 플로팅 챗봇에서 사용자 입력을 키워드 분석→8개 카테고리 분류→해당 페이지 네비게이션+파라미터 자동 실행하는 전체 흐름을 강화했다. URL 인코딩 버그 수정, 같은 페이지 재탐색 대응(force fresh navigation), 네비게이션 전용 카드 UI 추가, 시스템 프롬프트에 End-to-End 예시 5개 추가.

## 변경 파일 목록

### 백엔드
- `src/model/struct/agent/tools/navigate_to_page.py` — `urllib.parse.quote` 적용하여 공백/특수문자 URL 인코딩 처리
- `src/model/struct/agent.py` — 시스템 프롬프트 Workflow를 "STRICT" 모드로 강화, navigate 필수 호출 강제, 5개 End-to-End 예시 추가 (research/calculator/prediction/diagnosis/analysis)

### 프론트엔드
- `src/app/component.chat.floating/view.ts` — `navigateByUrl(url_string)` → `router.navigate([path], {queryParams})` 객체 방식으로 변경, force fresh navigation (루트→타겟 2단계), `pendingNavigation` 상태 관리, `navigateNow()` 즉시 이동 메서드 추가
- `src/app/component.chat.floating/view.pug` — `navigate_to_page` 결과 전용 카드 UI 추가 (🧭 아이콘 + 파라미터 표시 + "바로 이동" 버튼), 일반 tool_result과 분리 렌더링

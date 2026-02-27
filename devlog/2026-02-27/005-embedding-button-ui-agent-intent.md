# Embedding 청킹 옵션 상시 표출 + 버튼 UI / AI Agent 의도 분류 + 자동 페이지 이동

- **ID**: 005
- **날짜**: 2026-02-27
- **유형**: 기능 추가

## 작업 요약
1. Embedding 페이지의 고급 청킹 옵션을 아코디언 방식에서 항상 표출되는 방식으로 변경하고, 청킹 전략 선택을 드롭다운에서 버튼 그룹으로 교체 (FN-0004)
2. AI Agent 챗봇에 질문 의도 분류(주제발굴/공정예측/진단분석/이론연구) 뱃지 표시 및 답변 완료 후 해당 페이지 자동 이동 기능 추가 (FN-0005)

## 변경 파일 목록

### FN-0004: Embedding 페이지 UI 변경

**src/app/page.embedding/view.ts**
- `showAdvanced: boolean = false` 변수 제거

**src/app/page.embedding/view.pug**
- 아코디언 토글 버튼(button + svg + span) 삭제
- `*ngIf="showAdvanced"` 조건부 렌더링 제거, 청킹 옵션 영역 항상 표출
- `select` 드롭다운 → `button(*ngFor)` 버튼 그룹으로 교체
- 선택된 전략은 `bg-indigo-600 text-white` 하이라이트, 미선택은 `bg-white text-gray-600`

### FN-0005: AI Agent 의도 분류 + 자동 이동

**src/app/page.agent/view.ts**
- `assistantMsg`에 `intent: ''` 필드 추가
- `handleChatEvent`의 `navigate_to_page` tool_result 처리 시 `msg.intent = navData.page` 설정
- `done` 이벤트에서 `msg.navigations`가 있으면 2.5초 후 `navigateToPage()` 자동 호출
- `getIntentBadgeClass(page)` 메서드 추가: 도메인별 배경/텍스트/보더 색상 반환

**src/app/page.agent/view.pug**
- 어시스턴트 메시지의 텍스트 콘텐츠 앞에 의도 분류 뱃지 추가
- `getPageConfig(msg.intent).icon` + `label_ko` + "분석" 텍스트 표시
- "잠시 후 해당 페이지로 이동합니다" 안내 문구 표시

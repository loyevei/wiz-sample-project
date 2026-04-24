# 챗봇 프론트엔드를 Claude형 SSE 이벤트 흐름으로 정리

- **ID**: 004
- **날짜**: 2026-04-10
- **유형**: 리팩토링

## 작업 요약
`component.chat.sidebar`와 `component.chat.floating`의 SSE 이벤트 처리 로직을 Claude 분석서형 흐름에 맞게 정리했다. `text / tool_use / tool_result / done / history / error` 중심으로 동작하도록 보정했고, 다중 `text` 이벤트가 올 때 답변이 덮어써지지 않고 누적되도록 수정했다. 페이지 이동, 인자값, 페이지 결과 카드 출력은 그대로 유지했다.

## 변경 파일 목록
- `src/app/component.chat.sidebar/view.ts`
  - `pipeline` 이벤트는 상세 상태 문구 업데이트 용도로만 축소
  - `text` 이벤트를 누적 append 방식으로 변경
  - 페이지 결과 LLM 처리 상태 해제 로직 유지
- `src/app/component.chat.floating/view.ts`
  - `text` 이벤트를 stage 의존 대신 누적 append 방식으로 단순화
  - `pipeline` 이벤트는 프리뷰 설명 갱신 용도로 축소
  - 기존 카드 reveal 구조는 유지하되 core SSE 흐름 중심으로 정리

## 검증
- 무중단 빌드 성공: `EsBuild complete in 212ms`
- SSE 확인: `tool_use → tool_result → tool_use → tool_result → text → done`
- 프론트는 다중 `text` 이벤트를 안전하게 누적 처리하도록 반영 완료

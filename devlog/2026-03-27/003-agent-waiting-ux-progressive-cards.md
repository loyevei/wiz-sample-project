# 에이전트 답변 대기 체감 개선 UX 구현

- **ID**: 003
- **날짜**: 2026-03-27
- **유형**: 기능 추가

## 작업 요약
플로팅 챗봇과 v2 테스트 페이지에서 답변 생성 직후 답변 카드, 품질 카드, 페이지 결과 카드, 페이지 핸드오프 카드를 먼저 렌더링하고 스트리밍 이벤트에 따라 내용을 점진적으로 채우도록 개선했다.
최종 답변이 오기 전에도 `현재까지 핵심 포인트` 프리뷰를 보여주도록 상태를 확장해 사용자가 대기 중이라는 느낌을 덜 받게 했다.

## 변경 파일 목록
- `src/app/component.chat.floating/view.ts`
  - tool use/result, quality, pipeline, orchestration 이벤트를 프리뷰 텍스트와 placeholder 카드 상태에 반영하도록 확장
- `src/app/component.chat.floating/view.pug`
  - 답변/품질/페이지 결과/핸드오프 카드를 선렌더링하고 로딩 상태 문구를 표시하도록 UI 개선
- `src/app/page.agent.v2/view.ts`
  - 테스트용 SSE 페이지에도 previewContent, pageResultCard, navigationCard 상태와 이벤트 반영 로직 추가
- `src/app/page.agent.v2/view.pug`
  - v2 페이지에서 동일한 progressive card UX를 확인할 수 있도록 placeholder UI 추가

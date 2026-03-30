# 플로팅 챗봇 답변 타자식 표시

- **ID**: 007
- **날짜**: 2026-03-24
- **유형**: 기능 추가

## 작업 요약
플로팅 챗봇의 preview 및 최종답변이 한 번에 바뀌지 않고 타자식으로 점진적으로 표시되도록 구현했다.
assistant 메시지에 표시용 버퍼를 두고, SSE로 들어오는 텍스트를 타이핑 애니메이션으로 렌더링하도록 변경했다.

## 변경 파일 목록
- `src/app/component.chat.floating/view.ts`
  - `renderedContent`, `typingActive`, `typingTarget` 상태 추가
  - 타이핑 애니메이션 큐/정지/정리 helper 추가
  - preview/verification/error/fallback 텍스트 수신 시 표시 버퍼를 점진적으로 갱신하도록 수정
- `src/app/component.chat.floating/view.pug`
  - assistant 답변을 `renderedContent` 기준으로 렌더링하고, 타이핑 중 커서를 표시하도록 수정

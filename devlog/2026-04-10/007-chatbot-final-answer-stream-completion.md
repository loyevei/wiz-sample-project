# 챗봇 최종답변이 누락되던 SSE 종료 경로를 보강하고 플로팅 handoff 자동이동을 지연

- **ID**: 007
- **날짜**: 2026-04-10
- **유형**: 버그 수정

## 작업 요약
전용 챗봇 페이지와 플로팅 챗봇에서 SSE 스트림 종료 시점이 불안정하면 최종답변이 비어 보이거나 `done` 이벤트 없이 종료되는 경로가 남아 있던 문제를 수정했다.
프론트엔드는 `done/history/error`와 잔여 버퍼를 모두 안전하게 정리하도록 보강했고, 플로팅 챗봇은 `navigate_to_page` 결과를 받더라도 즉시 페이지를 이동하지 않고 최종답변을 먼저 사용자에게 남기도록 조정했다.

## 변경 파일 목록
- `src/app/page.agent.v2/view.ts`
  - SSE 응답/스트림 검증과 잔여 버퍼 flush를 보강해 마지막 chunk 이후에도 `text`, `history`, `done` 이벤트를 놓치지 않도록 수정
  - `done` 또는 `history`가 누락된 경우를 대비해 fallback 최종답변과 대화 이력을 안전하게 마무리하도록 보정
- `src/app/component.chat.floating/view.ts`
  - 플로팅 챗봇의 SSE 완료 처리와 카드 reveal 동기화를 보강해 최종답변, 품질 카드, handoff 카드가 종료 시점에 안정적으로 남도록 수정
  - `navigate_to_page` tool 결과 수신 후 즉시 라우팅하지 않고 최종답변 표시를 우선하도록 변경
- `src/app/page.agent.v2/api.py`
  - 서버 SSE generator에서 `history` 이벤트를 항상 보내고, `done`이 누락된 실행 경로에서는 fallback `done` 이벤트를 추가 전송하도록 보강
- `devlog.md`
  - 2026-04-10 작업 이력 007 추가

## 검증
- `wiz project build --project=main`
  - EsBuild 완료 및 프로젝트 빌드 성공 확인
- `/wiz/api/page.agent.v2/agent_chat` 실시간 SSE 확인
  - `orchestration -> tool_use -> tool_result -> text -> done -> history` 순서로 최종답변 이벤트 수신 확인
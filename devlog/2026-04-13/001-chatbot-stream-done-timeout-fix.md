# 챗봇 SSE done 타임아웃 마무리 보강

- **ID**: 001
- **날짜**: 2026-04-13
- **유형**: 버그 수정

## 작업 요약
챗봇 프론트엔드가 SSE의 done 이벤트를 받은 뒤에도 연결이 실제로 닫힐 때까지 chatLoading을 유지하고 있어, 마지막 답변이 화면에 표시된 뒤에도 로딩이 남는 경로가 있었다.

/agent, /agent/v2, 플로팅 AI Chat 모두에서 done 수신 즉시 UI 로딩을 종료하고, 짧은 grace timeout 뒤에도 스트림이 끝나지 않으면 reader.cancel()로 마무리하도록 보강했다. history 이벤트를 놓친 경우에는 프론트에서 현재 턴 기준 fallback history를 구성하도록 유지했다.

## 변경 파일 목록
- `src/app/page.agent/view.ts`
  - done 수신 즉시 로딩을 내리는 조기 완료 처리 추가
  - SSE reader에 400ms grace timeout + cancel 정리 경로 추가
- `src/app/page.agent.v2/view.ts`
  - done 수신 즉시 로딩을 내리는 조기 완료 처리 추가
  - SSE reader에 400ms grace timeout + cancel 정리 경로 추가
  - history 이벤트 미수신 시 현재 턴 기준 fallback history 구성 유지
- `src/app/component.chat.floating/view.ts`
  - 플로팅 AI Chat에도 동일한 조기 완료 처리 추가
  - SSE reader에 400ms grace timeout + cancel 정리 경로 추가
- 검증
  - `wiz project build --project=main` 빌드 성공
  - 브라우저에서 `/agent`, `/agent/v2` 모두 최종 답변 노출 및 로딩-only 상태 미재현 확인
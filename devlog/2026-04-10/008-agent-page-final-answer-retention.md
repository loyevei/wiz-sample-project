# 실제 AI 어시스턴트 페이지(/agent)에서 즉시 페이지 이동을 제거하고 최종답변 SSE 완료 처리를 보강

- **ID**: 008
- **날짜**: 2026-04-10
- **유형**: 버그 수정

## 작업 요약
실제 메뉴가 연결된 AI 어시스턴트 페이지 `/agent`는 `navigate_to_page` 도구 결과를 받자마자 페이지를 이동해 버려 최종답변이 화면에 남지 않았다.
`/agent` 페이지에도 SSE 잔여 버퍼 flush, `done/history` 누락 fallback, 자동 handoff 이동 제거를 적용해 최종답변과 `바로 이동` 버튼이 같은 화면에 함께 남도록 수정했다.

## 변경 파일 목록
- `src/app/page.agent/view.ts`
  - SSE 응답 상태 검증과 잔여 버퍼 flush를 추가해 마지막 이벤트가 잘리지 않도록 수정
  - `done/history` 수신 여부를 추적하고 누락 시 fallback 최종답변과 대화 이력을 보강하도록 수정
  - `navigate_to_page` tool 결과 수신 후 즉시 `navigateNow()` 하지 않고, handoff 카드를 남긴 뒤 사용자가 직접 이동하도록 변경
  - 최종답변/페이지결과/네비게이션 카드를 한 번에 마무리하는 `finalizeAssistantState()` 추가
- `src/app/page.agent/api.py`
  - SSE generator가 항상 `history` 이벤트를 보내고, `done`이 없으면 fallback `done` 이벤트를 추가 전송하도록 수정
- `devlog.md`
  - 2026-04-10 작업 이력 008 추가

## 검증
- `wiz project build --project=main`
  - EsBuild 완료 및 프로젝트 빌드 성공 확인
- 브라우저 실검
  - `/agent`에서 `안녕하세요` 전송 후 페이지가 `/agent`에 그대로 유지됨
  - `페이지 이동` 카드, `실행된 페이지 결과` 카드, `최종 답변` 카드가 순서대로 표시됨
  - 최종답변 본문과 `바로 이동` 버튼이 동시에 남는 것 확인
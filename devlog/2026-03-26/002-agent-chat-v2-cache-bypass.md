# agent_chat v2로 캐시 우회 + 결론 문단 보강

- **ID**: 002
- **날짜**: 2026-03-26
- **유형**: 버그 수정

## 작업 요약
서버 재시작 없이 백엔드 Python 변경사항이 적용되지 않는(런타임 캐시) 문제를 우회하기 위해, 새 앱 ID `page.agent.v2`를 추가하고 프론트(플로팅 챗봇)가 v2 엔드포인트를 호출하도록 변경했다. 또한 LLM 정제 프롬프트의 f-string 내 `{doc_id,...}` literal이 NameError를 유발하던 문제를 수정했고, JSON 파싱 실패(fallback) 경로에서도 `핵심 결론`이 최소 3문단으로 보강되도록 후처리를 보완했다.

## 변경 파일 목록
- project/main/src/app/page.agent.v2/app.json
- project/main/src/app/page.agent.v2/api.py
- project/main/src/app/page.agent.v2/view.ts
- project/main/src/app/page.agent.v2/view.pug
- project/main/src/app/page.agent.v2/view.scss
- project/main/src/app/page.agent.v2/view.html
- project/main/src/app/component.chat.floating/view.ts
- project/main/src/model/struct/agent.py

## 빌드 및 검증
- `wiz project build --project=main` (서버 재시작 없이)
- SSE 호출: `http://localhost:3000/wiz/api/page.agent.v2/agent_chat`
  - `핵심 결론`이 3문단(개괄→해석→다음 액션)으로 출력되는 것 확인

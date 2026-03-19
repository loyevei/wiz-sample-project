# 플로팅 챗봇 에이전트 f-string 오류 수정 및 응답 복구

- **ID**: 003
- **날짜**: 2026-03-18
- **유형**: 버그 수정

## 작업 요약
플로팅 챗봇이 `page.agent/agent_chat`를 통해 Tool-Use 기반 에이전트 응답을 받는 구조를 재점검했고, 시스템 프롬프트 생성 중 발생하던 `name 'Te' is not defined` 런타임 오류를 수정했다.
`agent.py`의 f-string 안에 JSON 예시를 그대로 넣어 발생한 NameError를 이스케이프 처리로 해결했고, 서버 재시작 없이 normal build와 캐시 갱신 후 실제 SSE 응답이 정상 동작함을 확인했다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - 시스템 프롬프트 예시의 JSON/params 중괄호를 이스케이프해 f-string NameError 수정
- `bundle/src/model/struct/agent.py`
  - 빌드 반영 후 런타임 번들에서 패치 확인
- `bundle/www/main.js`
  - normal build 후 최신 프런트 번들 반영
- `.github/task/todo.md`
  - 작업 항목 등록 및 완료 후 다음 템플릿 번호로 정리
- `.github/task/worked/FN-20260318-0003.md`
  - 완료 작업 아카이브 작성

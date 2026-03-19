# 플로팅 챗봇 에이전트형 응답 강화

- **ID**: 002
- **날짜**: 2026-03-19
- **유형**: 기능 추가

## 작업 요약
플로팅 챗봇 에이전트가 페이지 이동만 하고 끝나지 않도록 시스템 프롬프트와 네비게이션 결과를 보강했다.
`navigate_to_page` 이후에도 분류, 키워드, 도구 결과, 대상 페이지, 현재 컬렉션을 포함한 handoff 메시지를 남기도록 규칙을 추가하고, 프론트엔드에는 비어 있는 응답을 메우는 요약 fallback을 넣었다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - 최신 시스템 프롬프트를 매 요청마다 갱신
  - `navigate_to_page` 이후 final handoff 메시지를 강제하는 규칙 추가
- `src/model/struct/agent/tools/navigate_to_page.py`
  - 현재 collection을 명시적으로 결과와 params에 포함
- `src/app/component.chat.floating/view.ts`
  - 에이전트 요약 fallback 생성 및 네비게이션 collection 반영
- `build/src/model/struct/agent.py`
- `build/src/model/struct/agent/tools/navigate_to_page.py`
  - 빌드 API 복사 실패를 우회하기 위해 최신 Python 변경을 수동 동기화
- `build/dist/build/main.js`
- `bundle/www/main.js`
  - 서버 재시작 없이 프론트 번들을 재생성·반영

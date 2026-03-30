# 에이전트 도구 모듈 `wiz` 전역 주입 복구

- **ID**: 012
- **날짜**: 2026-03-24
- **유형**: 버그 수정

## 작업 요약
플로팅 챗봇 실행 중 `name 'wiz' is not defined` 오류가 발생한 원인을 추적한 결과, `read_page_results` 같은 에이전트 도구 모듈이 `importlib`로 일반 파이썬 모듈처럼 로드되면서 WIZ 실행 환경의 전역 `wiz`를 자동으로 받지 못하는 문제가 있었다.
도구 컨텍스트와 모듈 로딩 시점에 `wiz`를 명시적으로 주입해, 도구 내부에서 `wiz.project.fs()` 같은 WIZ API를 런타임에 안전하게 사용할 수 있도록 수정했다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - `_tool_context`에 `wiz` 추가
  - `_load_tools()`에서 각 도구 모듈 로드 전 `mod.wiz = wiz` 주입
  - `read_page_results.py` 등 도구 내부의 전역 `wiz` 참조가 런타임에 정상 동작하도록 복구
- `.github/task/todo.md`
  - 다음 작업 번호 템플릿으로 갱신
- `devlog.md`
  - 2026-03-24 작업 인덱스 012 추가

## 검증
- `src/model/struct/agent.py` 정적 오류 없음
- `src/model/struct/agent/tools/read_page_results.py` 정적 오류 없음
- `wiz project build --project=main` 성공

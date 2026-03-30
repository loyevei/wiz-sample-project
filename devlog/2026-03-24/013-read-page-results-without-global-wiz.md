# `read_page_results` 전역 `wiz` 의존 제거

- **ID**: 013
- **날짜**: 2026-03-24
- **유형**: 버그 수정

## 작업 요약
플로팅 챗봇 retriever 단계에서 `페이지 결과 추출 오류(name 'wiz' is not defined)`가 발생한 원인을 추적한 결과, `read_page_results` 도구가 프로젝트 루트를 찾고 page API 모듈을 로드할 때 전역 `wiz` 이름에 직접 의존하고 있었다.
도구 내부에서 `self.ctx['wiz']`를 우선 사용하고, 필요 시 `globals()['wiz']`로 fallback 하도록 수정했으며, 프로젝트 루트도 `__file__` 기반으로 계산해 전역 `wiz` 없이도 동작하도록 보강했다.

## 변경 파일 목록
- `src/model/struct/agent/tools/read_page_results.py`
  - `_get_wiz()` helper 추가
  - `_get_project_root()` helper 추가
  - `_load_module()`가 전역 `wiz` 대신 tool context의 `wiz`를 우선 사용하도록 수정
  - page result 추출 시 프로젝트 루트 계산이 전역 `wiz.project.fs()`에 의존하지 않도록 변경
- `.github/task/todo.md`
  - 다음 작업 번호 템플릿으로 갱신
- `devlog.md`
  - 2026-03-24 작업 인덱스 013 추가

## 검증
- `src/model/struct/agent/tools/read_page_results.py` 정적 오류 없음
- `src/model/struct/agent.py` 정적 오류 없음
- `wiz project build --project=main` 성공

# 신규 컬렉션 문자열 메타에도 플로팅 챗봇 경로가 깨지지 않도록 정규화 및 fallback 보강

- **ID**: 012
- **날짜**: 2026-03-26
- **유형**: 버그 수정

## 작업 요약
신규 컬렉션에서 `collection_meta.json` 엔트리가 dict가 아니라 문자열(model name) 형태로 들어와도, 플로팅 챗봇과 관련 페이지/API/에이전트 도구가 `info.get(...)` 호출에서 깨지지 않도록 collection meta 정규화를 전반에 적용했다.
또한 플로팅 챗봇의 컬렉션 목록 로딩에서 `/wiz/api/page.embedding/collections`가 비정상 응답을 반환해도 자체 `collections` API로 자동 fallback 하도록 보강해, 서버 재시작 없이도 신규 컬렉션 질문 흐름이 끊기지 않게 했다.

## 변경 파일 목록
- `src/app/component.chat.floating/api.py`
  - collection meta 엔트리가 문자열이어도 dict처럼 다룰 수 있도록 `_normalize_collection_info()` 추가
- `src/app/component.chat.floating/view.ts`
  - `/wiz/api/page.embedding/collections` 응답이 200이 아니면 `wiz.call("collections")`로 자동 fallback 하도록 보강
- `src/app/page.embedding/api.py`
  - `_load_collection_meta()` / `_get_collection_model()` / `collections()`에서 문자열 meta 엔트리 정규화
- `src/app/page.research/api.py`
  - collection meta 로딩/모델 결정/컬렉션 목록 조회에서 문자열 엔트리 정규화
- `src/app/page.theory/api.py`
  - collection meta 로딩/모델 결정/컬렉션 목록 조회에서 문자열 엔트리 정규화
- `src/app/page.prediction/api.py`
  - collection meta 로딩/모델 결정/컬렉션 목록 조회에서 문자열 엔트리 정규화
- `src/app/page.diagnosis/api.py`
  - collection meta 로딩/모델 결정/컬렉션 목록 조회에서 문자열 엔트리 정규화
- `src/model/struct/agent/tools/*.py`
  - `get_collections`, `search_papers`, `recommend_topics`, `analyze_keywords`, `search_equations`, `search_anomaly`, `extract_assumptions`, `generate_hypothesis`, `compare_diagnostics`, `inverse_search`, `predict_process`, `extract_equations_ext`, `analyze_parameter_effect`, `build_theory_graph`, `detect_research_gaps`, `failure_reasoning`에 문자열 meta 엔트리 정규화 추가

## 검증
- `wiz project build --project=main`
- 문자열 meta 엔트리 재현 검증
  - `page.agent.v2/agent_chat` 에서 신규 컬렉션(`test2`) 질의가 오류 없이 완료됨
  - `/wiz/api/page.embedding/collections` 비정상 응답 시 플로팅 컴포넌트가 자체 `collections` API로 fallback 하도록 보강
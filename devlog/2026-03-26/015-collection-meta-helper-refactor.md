# collection_meta 정규화 공통 helper 정리

- **ID**: 015
- **날짜**: 2026-03-26
- **유형**: 리팩토링

## 작업 요약
`collection_meta.json`의 엔트리가 dict 또는 문자열(model name) 형태로 들어올 수 있어, 여러 페이지 API와 agent tool 파일들에 같은 정규화 함수가 반복되어 있었다.
이번 작업에서는 페이지/API 계층에는 `src/model/collectionmeta.py` WIZ model helper를 추가하고, agent tool 계층에는 `src/model/struct/agent/tools/common.py`를 추가해 문자열→dict 정규화 로직을 공통화했다. 이로써 동일한 예외 대응을 한 곳에서 유지할 수 있게 됐고, 향후 메타 형식이 바뀌더라도 수정 지점이 줄어들었다.

## 변경 파일 목록
- `src/model/collectionmeta.py`
  - `normalize_info()`, `normalize_meta()`, `load()`, `get_model()` 공통 helper 추가
- `src/app/component.chat.floating/api.py`
  - 컬렉션 목록 응답 시 공통 helper를 사용해 meta 엔트리 정규화
- `src/app/page.embedding/api.py`
- `src/app/page.research/api.py`
- `src/app/page.prediction/api.py`
- `src/app/page.diagnosis/api.py`
- `src/app/page.theory/api.py`
  - `_load_collection_meta()` / `_get_collection_model()` 및 collections 메타 조회에서 공통 helper 사용
- `src/model/struct/agent/tools/common.py`
  - agent tool용 `normalize_collection_info()` 추가
- `src/model/struct/agent/tools/*.py`
  - 개별 `_normalize_collection_info()` 중복 제거 후 공통 helper import로 교체

## 검증
- `python3 -m py_compile /opt/app/project/main/src/model/collectionmeta.py /opt/app/project/main/src/app/component.chat.floating/api.py /opt/app/project/main/src/app/page.embedding/api.py /opt/app/project/main/src/app/page.research/api.py /opt/app/project/main/src/app/page.prediction/api.py /opt/app/project/main/src/app/page.diagnosis/api.py /opt/app/project/main/src/app/page.theory/api.py /opt/app/project/main/src/model/struct/agent/tools/common.py /opt/app/project/main/src/model/struct/agent/tools/search_papers.py /opt/app/project/main/src/model/struct/agent/tools/compare_diagnostics.py /opt/app/project/main/src/model/struct/agent/tools/get_collections.py /opt/app/project/main/src/model/struct/agent/tools/analyze_keywords.py /opt/app/project/main/src/model/struct/agent/tools/analyze_parameter_effect.py /opt/app/project/main/src/model/struct/agent/tools/build_theory_graph.py /opt/app/project/main/src/model/struct/agent/tools/detect_research_gaps.py /opt/app/project/main/src/model/struct/agent/tools/extract_assumptions.py /opt/app/project/main/src/model/struct/agent/tools/extract_equations_ext.py /opt/app/project/main/src/model/struct/agent/tools/failure_reasoning.py /opt/app/project/main/src/model/struct/agent/tools/generate_hypothesis.py /opt/app/project/main/src/model/struct/agent/tools/inverse_search.py /opt/app/project/main/src/model/struct/agent/tools/predict_process.py /opt/app/project/main/src/model/struct/agent/tools/recommend_topics.py /opt/app/project/main/src/model/struct/agent/tools/search_anomaly.py /opt/app/project/main/src/model/struct/agent/tools/search_equations.py`
- `cd /opt/app/project/main && wiz project build --project=main`

## 변경 패턴
- Before
  - 페이지/API와 agent tool 파일마다 동일한 `_normalize_collection_info()` 구현이 반복됨
- After
  - 페이지/API는 WIZ model helper, agent tools는 tools 공용 helper를 재사용
# `read_page_results` Diagnosis Failure 확장

- **ID**: 004
- **날짜**: 2026-03-23
- **유형**: 기능 추가

## 작업 요약
`diagnosis/failure` 탭이 실제로 보여주는 고장 분석 결과를 에이전트가 직접 읽을 수 있도록 공용 함수를 추가하고 `read_page_results`를 확장했다.
이제 증상 기반 고장 진단 질문에서도 매칭 패턴, 근거 문서, 스펙트럼 요약을 페이지 로직 그대로 읽어 OpenAI 한글 최종답변에 반영할 수 있다.

## 변경 파일 목록
- `src/app/page.diagnosis/api.py`
  - `run_failure_reasoning_data()` 추가
  - 기존 `failure_reasoning()`이 공용 함수를 재사용하도록 정리
- `src/model/struct/agent/tools/read_page_results.py`
  - `diagnosis/failure` 지원 추가
  - summary, matched_patterns, evidence_docs, spectrum_info를 정규화해 반환
- `src/model/struct/agent.py`
  - diagnosis 페이지 결과 읽기 가이드에 failure 탭 반영

## 변경 패턴
- Before
  - `failure` 탭은 페이지 내부 API 호출 결과를 에이전트가 직접 재사용하지 못했다.
- After
  - 에이전트가 `diagnosis/failure`의 실제 결과 JSON을 읽고, 증상 기반 고장 원인/해결 힌트를 포함한 한글 최종답변을 생성할 수 있다.

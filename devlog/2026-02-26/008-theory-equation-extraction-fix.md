# Theory 페이지 수식 추출 버그 수정

- **ID**: 008
- **날짜**: 2026-02-26
- **유형**: 버그 수정

## 작업 요약
Theory 페이지에서 test_papers 컬렉션의 수식이 0개로 표시되던 버그를 수정했다. 원인은 두 가지로, (1) `chunk_index == 0` 필터로 문서당 첫 번째 청크만 조회하여 수식 전용 청크(chunk_index >= 1)를 누락, (2) `_extract_latex_equations()`가 Embedding에서 저장하는 `[EQUATION: ...]` 마커 형식을 인식하지 못함이었다.

## 변경 파일 목록

### 수정: `src/app/page.theory/api.py`

**헬퍼 함수 추가**
- `_get_collection_fields()`: 컬렉션 스키마 필드명 조회 (chunk_type 존재 여부 판별용)
- `_query_all_chunks()`: Milvus limit 16384 대응 페이지네이션 전체 조회

**`_extract_latex_equations()` 수정**
- `[EQUATION: eq_N | type=display | $$latex$$ | context: ...]` 마커 형식 인식 추가 (최우선 패턴)
- `[FORMULA: ...]` 마커도 동시 지원
- `seen_latex` set으로 중복 수식 제거

**`extract_equations()` 수정**
- `chunk_index == 0` 필터 제거
- chunk_type 필드가 있는 컬렉션: `chunk_type == "formula"` 우선 조회 + 나머지 청크 중 수식 마커 포함 청크 추가
- 구 스키마 컬렉션: 전체 청크 조회
- 응답 최대 200개로 증가 (기존 100개)

**`equation_stats()` 수정**
- 동일한 스키마 인식 + 전체 청크 조회 로직 적용

**`assumption_stats()` 수정**
- `chunk_index == 0` → `_query_all_chunks(filter_expr="chunk_index >= 0")` 변경

**`extract_assumptions()` 수정**
- doc_ids 미지정 시 `chunk_index == 0` → `chunk_index >= 0` 변경
- `_query_all_chunks()` 사용으로 limit 제한 해소

**`build_theory_graph()` 수정**
- `chunk_index == 0` + `chunk_index == 1` 2회 조회 → `_query_all_chunks()` 전체 청크 1회 조회로 통합

## 테스트 결과
- test_papers: 0개 → **136개 수식** 추출 (10개 문서에서 발견)
- equation_stats: 132 other, 2 empirical, 2 constitutive 분류
- assumption_stats: 132개 가정 (12개 문서에서 발견)

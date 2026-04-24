# Hybrid 본문 추출 파이프라인 분리

- **ID**: 002
- **날짜**: 2026-04-24
- **유형**: 리팩토링

## 작업 요약
`_extract_text_from_pdf()`를 3단계로 분리: Phase 1(PyMuPDF 레이아웃), Phase 2(Nougat 추출), Phase 3(소스 병합). 텍스트 우선순위는 Nougat → native → Surya.

## 변경 파일 목록
### api.py (src/app/page.embedding/api.py)
- `_extract_layout_from_pdf()`: Phase 1 — PyMuPDF 레이아웃만 추출
- `_run_nougat_extraction()`: Phase 2 — Nougat 페이지별 텍스트 맵 반환
- `_preferred_page_text()`: 페이지별 최적 텍스트 소스 선택
- `_merge_page_texts()`: Phase 3 — 소스 병합, nougat/native/failed 페이지 수 반환
- `_extract_text_from_pdf()`: 오케스트레이터 (Phase 1→2→3)
- `upload()`: `extraction_mode`, `use_nougat`, `gemma_rescue` 파라미터 추가

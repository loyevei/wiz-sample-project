# 최종답변에서 PDF 논문 근거 노출 제거 및 한국어-only 고정

- **ID**: 001
- **날짜**: 2026-03-24
- **유형**: 기능 추가

## 작업 요약
플로팅 챗봇의 최종답변에서 PDF 논문 제목, 파일명, 원문 인용 조각, 영어 문헌 목록이 직접 노출되지 않도록 정리했다.
최종답변은 페이지 결과를 바탕으로 하되, 사용자가 보게 되는 설명 문장은 모두 한국어로만 구성되도록 refinement 지시문과 후처리 정규화를 강화했다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - 최종답변 지시문에서 paper titles / filenames / raw snippets 허용 문구 제거
  - `_strip_document_references()` 추가로 PDF 파일명, 영문 문헌 목록, raw source line 제거
  - `_normalize_final_answer_korean()`가 navigation CTA 제거와 함께 문헌 식별자 제거 후처리를 수행하도록 확장
  - quality/fallback 문구에서 파일명 기반 근거 노출 제거

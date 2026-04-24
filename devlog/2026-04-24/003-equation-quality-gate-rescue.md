# 수식 품질 게이트 및 Gemma 4 Rescue 구현

- **ID**: 003
- **날짜**: 2026-04-24
- **유형**: 기능 추가

## 작업 요약
수식 LaTeX 품질 판정 함수(`_is_equation_quality_ok`)와 Gemma Vision 재추출 함수(`_run_gemma_equation_rescue`)를 Phase 2.5로 추가. 품질 미달 수식만 선별적으로 rescue.

## 변경 파일 목록
### api.py (src/app/page.embedding/api.py)
- `_is_equation_quality_ok(latex)`: 괄호 짝, 수학 기호 유무, 노이즈 비율, 최소 길이 검사
- `_run_gemma_equation_rescue(pdf_path, pages_data)`: bbox crop → Gemma `equation()` → 블록 in-place 갱신, rescue/skipped/failed 통계 반환
- 오케스트레이터에 Phase 2.5 호출 추가
- 업로드 응답에 `gemma_rescues`, `rescue_skipped`, `rescue_failed` 필드 추가

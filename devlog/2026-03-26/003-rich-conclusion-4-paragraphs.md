# 핵심 결론 4문단 고정 + top_terms/추가 키워드 제안

- **ID**: 003
- **날짜**: 2026-03-26
- **유형**: 버그 수정

## 작업 요약
최종 답변의 `핵심 결론`이 케이스에 따라 1~3문단으로 짧게 끝나거나, PDF 파일명/원문 스니펫이 노출되는 문제가 있었다. 페이지 결과가 존재할 때는 안전장치로 `핵심 결론`을 최소 4문단(개괄→해석→테마/키워드 또는 제안→다음 액션)으로 보강하고, 파일명(.pdf) 및 원문 스니펫(긴 영어 시퀀스 + '—' 형태)이 감지되면 강제 재구성하도록 수정했다.

## 변경 파일 목록
- project/main/src/model/struct/agent.py
  - `_ensure_rich_korean_conclusion()` 강화
    - 파일명/메타(.pdf, filename=, file= 등) 아티팩트 감지 시 강제 재구성
    - 원문 스니펫(긴 영어 + '—') 감지 시 강제 재구성
    - `핵심 결론` 유지 조건을 4문단 이상으로 강화
    - 한국어 조사(20건을/다수의 결과를) 보정
  - `_build_page_grounded_fallback_answer()`에서 filename 노출 제거(상위 문헌 묶음 N 형태로 대체)
  - `_strip_document_references()`에서 .pdf 토큰 포함 라인 제거 강화

## 빌드 및 검증
- `wiz project build --project=main` (서버 재시작 없이)
- SSE(v2) 검증: `/wiz/api/page.agent.v2/agent_chat`
  - `.pdf` 미노출 확인
  - `핵심 결론` 문단형 출력 보강 확인

# 에이전트 챗봇 페이지 조회 결과 요약 강화

- **ID**: 002
- **날짜**: 2026-04-23
- **유형**: 기능 개선

## 작업 요약
에이전트가 `read_page_results`로 가져온 페이지 조회 결과를 모든 페이지/탭 데이터 구조(clusters, papers, predictions, results, matched_patterns 등)에 맞게 파싱해 최종 답변에 풍부한 요약 블록을 항상 주입하도록 개선. 사용자가 페이지로 이동하지 않고도 챗봇 답변만 보고 핵심 결과(파일명/유사도/연도/스니펫/원인/해결 등)를 파악할 수 있다.

## 변경 파일 목록

### Backend
- `src/model/struct/agent.py`
  - `_format_score()` 신규: 점수 포맷 헬퍼 (0~1 범위는 %, 그 외는 소수)
  - `_summarize_page_result()` 신규: 단일 페이지 결과 → Markdown 요약 (페이지/탭별 분기: research/discover→clusters, research/recommend→papers, prediction→predictions, theory→results, diagnosis/failure→matched_patterns 등)
  - `_build_page_results_summary()` 신규: 여러 페이지 결과를 통합 Markdown 블록으로 묶음
  - `_finalize_answer_text()` 수정: 페이지 결과가 있으면 LLM 참조 여부와 무관하게 항상 답변 앞에 요약 블록 삽입 (중복 헤더 방지)
  - `_build_fallback_answer()` 수정: 새 헬퍼로 통일

## Before / After

### Before
- `results`/`data` 키만 처리 → research/discover(`clusters`), research/recommend(`papers`), prediction(`predictions`), diagnosis/failure(`matched_patterns`) 결과 모두 누락
- LLM이 "결과/건/검색" 등 키워드를 답변에 쓰면 요약 자체를 건너뜀
- 항목 표시는 `title/name/doc_id`만, 점수 외 메타(연도, 스니펫, 원인, 해결, 추출값) 없음

### After
- 페이지/탭별로 알맞은 컬렉션 키를 선택 (`clusters`/`papers`/`predictions`/`results`/`matched_patterns`/`history`)
- 항목별로 파일명·유사도·연도·스니펫(180자 트림)·원인/해결/추출값/수식 개수까지 포함
- 페이지 결과가 있으면 항상 `📊 페이지 조회 결과` 헤더 + `---` 구분선으로 답변 앞에 삽입

## 동기화 / 빌드
- `src/model/struct/agent.py` → `bundle/src/model/struct/agent.py`, `build/src/model/struct/agent.py` 수동 복사
- 서버 재시작 없이 즉시 반영됨 (실제 호출 검증 완료)

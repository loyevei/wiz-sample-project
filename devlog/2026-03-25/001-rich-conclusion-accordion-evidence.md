# 최종 답변 품질 개선: 문단형 결론 + 아코디언 근거 UI

- **ID**: 001
- **날짜**: 2026-03-25
- **유형**: 기능 추가

## 작업 요약
에이전트 최종 답변의 핵심 결론을 bullet 1줄에서 여러 문단 서술형으로 변경하고, 근거 문헌을 아코디언 UI로 개별 문서 상세(파일명, 유사도, 스니펫)를 전부 펼쳐볼 수 있도록 개선했다.

## 변경 파일 목록

### 백엔드 (agent.py)
- `_refine_final_answer()` 시스템 프롬프트: `answer` 구조를 "핵심 결론 1줄 + 근거 2~3줄" → "핵심 결론 여러 문단(개괄→주제별→시사점) + 근거 요약 2~3줄" + `evidence_items` JSON 배열 반환 지시
- `_build_page_grounded_fallback_answer()`: 결론을 paragraph 리스트로 재구성 (clusters/predictions/results/matched_patterns 분기)
- `_build_fast_final_answer()`: bullet prefix `- ` 제거하여 문단형으로 출력
- `_normalize_final_answer_korean()`: 시스템 프롬프트를 문단 구조로 변경, max_tokens 700→1500
- `_normalize_final_answer_language()`: 영어 프롬프트도 문단 구조로 변경
- `_ensure_page_result_summary_in_answer()`: 문단 기반 파싱으로 재작성, `• ` bullet도 처리, `페이지 결과 요약:` 중복 방지
- `_build_evidence_items_from_page_results()`: 신규 — 페이지 결과에서 개별 문서 {doc_id, filename, score, snippets} 추출
- SSE `evidence_items` 이벤트: quality 이벤트 직후 yield, 모든 경로(priority/fast/refine)에서 report에 evidence_items 포함

### 프론트엔드 (view.ts / view.pug)
- `handleChatEvent()`: `evidence_items` 이벤트 타입 처리 → `msg.evidenceItems` + `msg.evidenceOpen` 설정
- `toggleEvidence()`, `formatEvidenceScore()`: 아코디언 토글 및 유사도 포맷 메서드 추가
- `buildPageResultFallbackAnswer()`: 문단형 구조로 변경
- `view.pug`: 최종 답변 카드 아래에 아코디언 근거 문헌 UI (📚 아이콘, 접기/펼치기, 개별 문서 카드)

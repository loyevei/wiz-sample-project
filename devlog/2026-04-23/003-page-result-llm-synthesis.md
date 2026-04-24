# 페이지 결과 LLM 자연어 요약 추가

- **ID**: 003
- **날짜**: 2026-04-23
- **유형**: 기능 개선

## 작업 요약
구조화된 페이지 결과 리스트 위에 LLM이 결과를 해석한 자연어 요약(`✨ AI 요약`)을 추가. 사용자가 결과의 핵심 패턴·주제·추천 포인트를 즉시 파악할 수 있도록 개선.

## 변경 파일 목록

### Backend
- `src/model/struct/agent.py`
  - `_generate_page_synthesis()` 신규: 페이지 결과를 짧은 LLM 호출(max_tokens=400, temperature≤0.3)로 3~5문장 요약 생성. 실패 시 빈 문자열 반환하여 본 흐름에 영향 없음
  - `_build_synthesis_input()` 신규: LLM 입력용 plain 텍스트 빌더 (페이지/탭/질의/총건수 + 항목별 제목·연도·점수·스니펫 240자)
  - `_build_page_results_summary()` 시그니처 확장: `synthesis` 파라미터 추가, 출력 구조를 `📊 페이지 조회 결과 → ✨ AI 요약 → 📝 상세 결과` 3단 섹션으로 재구성
  - `run()` 메인 루프: `read_page_results` 완료 직후 `_generate_page_synthesis()` 호출 → `collected["page_synthesis"]`에 저장 (try/except로 실패 무시)
  - `_finalize_answer_text()` / `_build_fallback_answer()`: synthesis 인자를 `_build_page_results_summary`에 전달

## Before / After

### Before
```
📊 페이지 조회 결과
1. 논문 A (72.1%) · 2017 > snippet...
2. 논문 B (69.5%) · 2023 > snippet...
...
```

### After
```
📊 페이지 조회 결과

✨ AI 요약
제공된 검색 결과는 '플라즈마 식각' 키워드에 대해 물리적/화학적 표면 특성 및 비정질 구조 연구를 중심으로 분포되어 있습니다.
* 핵심 패턴: 식각 메커니즘을 다룬 2017년 SiO2 식각률 연구 외 대부분이 표면 흡착·비정질 구조 등 기초 과학 논문
* 추천 포인트: 식각 공정의 물리적 변수에 집중한다면 1번 논문 우선, 표면 화학 특성 이해가 목적이면 2023년 이후 Applied Surface Science 논문 참고 권장

📝 상세 결과
1. 논문 A (72.1%) · 2017 > snippet...
2. 논문 B (69.5%) · 2023 > snippet...
...
```

## 동기화 / 빌드
- `src/model/struct/agent.py` → `bundle/`, `build/` 수동 복사
- 서버 재시작 없이 즉시 반영, 실제 호출(`플라즈마 식각 공정에 대한 논문 추천해줘`)로 AI 요약 블록 정상 출력 검증

## 비고
- 추가 LLM 호출 1회 발생 → 로컬 Gemma 사용 시 응답 시간 추가 (기존 흐름의 약 1/4 수준 단축 프롬프트로 최소화)
- 실패해도 본 흐름에 영향 없음 (try/except + 빈 문자열 반환)

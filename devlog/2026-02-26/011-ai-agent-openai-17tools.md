# AI Agent — OpenAI 전환 + 17개 도구 통합 (4대 연구 기능)

- **ID**: 011
- **날짜**: 2026-02-26
- **유형**: 기능 추가

## 작업 요약
Anthropic Claude 기반 AI Agent를 OpenAI GPT-4o 기반으로 전면 전환하고, 기존 4개 도구에 13개 신규 도구를 추가하여 총 17개 도구로 확장했다. 사이트의 4대 핵심 페이지(주제 발굴/공정 예측/진단 분석/이론 연구)의 분석 기능을 모두 Agent Tool로 이식하여, 챗봇 하나로 전체 연구 기능을 수행할 수 있게 만들었다.

## 변경 파일 목록

### Config (LLM 프로바이더 전환)
| 파일 | 변경 내용 |
|------|----------|
| `config/season.py` | `anthropic_api_key/model` → `openai_api_key/openai_model("gpt-4o")` |

### Agent Core (OpenAI SDK 전환)
| 파일 | 변경 내용 |
|------|----------|
| `src/model/struct/agent.py` (297줄, 전면 재작성) | `from openai import OpenAI` 클라이언트, Function Calling API 형식, `tool_calls` 배열 파싱, `tool` role 결과 전송, `finish_reason=="stop"` 종료 조건, 4대 기능별 도구 조합 가이드 포함 System Prompt |
| `src/model/struct/agent/tools/base_tool.py` (751 bytes) | `to_claude_tool()` → `to_openai_tool()` 반환 형식 변경 (`{"type":"function","function":{...}}`) |

### 신규 도구 — 주제 발굴(Research) 3개
| 파일 | 도구명 | 기능 |
|------|--------|------|
| `tools/recommend_topics.py` (7562 bytes) | recommend_topics | 공출현 용어 추출 → 교차 검색 → 연구 공백 → 확장 템플릿(최적화/모니터링/ML/시뮬레이션) |
| `tools/detect_research_gaps.py` (5931 bytes) | detect_research_gaps | 키워드별 KNN 밀도 + 교차 조합 gap_score → 잠재력 등급(높음/보통/낮음) |
| `tools/generate_hypothesis.py` (7122 bytes) | generate_hypothesis | 벡터 검색 → novel terms → 5가지 가설 템플릿 자동 생성 |

### 신규 도구 — 공정 예측(Prediction) 4개
| 파일 | 도구명 | 기능 |
|------|--------|------|
| `tools/predict_process.py` (10865 bytes) | predict_process | 자연어 공정 조건 → 벡터 검색 → PARAM_PATTERNS(11종) 정규식 파라미터 추출 |
| `tools/analyze_parameter_effect.py` (4981 bytes) | analyze_parameter_effect | 4방향 검색(effect/increase/decrease/optimal) 통합 분석 |
| `tools/inverse_search.py` (9662 bytes) | inverse_search | 목표 결과 → 가중 평균/표준편차 → 추천 공정 조건 범위 + 신뢰도 |
| `tools/surrogate_predict.py` (8785 bytes) | surrogate_predict | Ridge 회귀 → 예측값 + 95% CI + R² + 변수 중요도 |

### 신규 도구 — 진단 분석(Diagnosis) 3개
| 파일 | 도구명 | 기능 |
|------|--------|------|
| `tools/compare_diagnostics.py` (8040 bytes) | compare_diagnostics | 다중 쿼리 검색 → TF 키워드 추출 → 고유/공통 분리 → 구조화 비교 |
| `tools/search_anomaly.py` (4895 bytes) | search_anomaly | 4방향 쿼리(원인/해결/진단/이상) → 중복 제거 통합 |
| `tools/failure_reasoning.py` (6355 bytes) | failure_reasoning | FAILURE_KEYWORDS 패턴 매칭 → 원인분석/해결방법/관련자료 태그 분류 |

### 신규 도구 — 이론 연구(Theory) 3개
| 파일 | 도구명 | 기능 |
|------|--------|------|
| `tools/extract_equations_ext.py` (9571 bytes) | extract_equations | 4종 LaTeX 추출 + PLASMA_EQUATIONS(12종) 분류 + 5 EQUATION_CATEGORIES |
| `tools/extract_assumptions.py` (11197 bytes) | extract_assumptions | ASSUMPTION_DICT(15종) + TRIGGER_PATTERNS(7종) → 가정 추출 + 상충 검사 |
| `tools/build_theory_graph.py` (9011 bytes) | build_theory_graph | PLASMA_CONCEPTS(40+) + CAUSAL_PATTERNS(5종) → BFS 이론 그래프 탐색 |

### 기존 도구 (변경 없음, 호환성 확인)
| 파일 | 도구명 | 상태 |
|------|--------|------|
| `tools/search_papers.py` | search_papers | BaseTool 상속 → to_openai_tool() 자동 적용 ✅ |
| `tools/get_collections.py` | get_collections | BaseTool 상속 → to_openai_tool() 자동 적용 ✅ |
| `tools/search_equations.py` | search_equations | BaseTool 상속 → to_openai_tool() 자동 적용 ✅ |
| `tools/analyze_keywords.py` | analyze_keywords | BaseTool 상속 → to_openai_tool() 자동 적용 ✅ |

## 핵심 변경 패턴

### OpenAI Function Calling 메시지 형식
```python
# Anthropic → OpenAI 주요 차이
# 1. System message: 별도 param → messages[0]에 {"role":"system"} 삽입
# 2. Tool 스키마: {"name","description","input_schema"} → {"type":"function","function":{"name","description","parameters"}}
# 3. 도구 호출: response.content[type=="tool_use"] → choice.message.tool_calls[].function
# 4. 도구 결과: {"role":"user", content:[{"type":"tool_result"}]} → {"role":"tool","tool_call_id":...,"content":...}
# 5. 종료 조건: stop_reason=="end_turn" → finish_reason=="stop"
```

## 테스트 결과
- Python import: 17개 도구 전체 로드 성공
- API curl (`agent_tools`): 17개 도구 반환, code 200
- 도구 이름 목록: analyze_keywords, analyze_parameter_effect, build_theory_graph, compare_diagnostics, detect_research_gaps, extract_assumptions, extract_equations, failure_reasoning, generate_hypothesis, get_collections, inverse_search, predict_process, recommend_topics, search_anomaly, search_equations, search_papers, surrogate_predict

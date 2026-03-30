# 플로팅 챗봇 하이브리드/계층형 에이전트 구조 리팩토링

- **ID**: 019
- **날짜**: 2026-03-26
- **유형**: 리팩토링

## 작업 요약
기존 3541줄 모놀리식 `agent.py`를 하이브리드/계층형 에이전트 아키텍처로 리팩토링.
오케스트레이터(최상위) + 5개 서브 에이전트 구조로 분리하여 관심사 분리, 확장성, 유지보수성을 개선.
기존 SSE 이벤트 체계 및 프론트엔드(component.chat.floating, page.agent.v2)와의 완전 호환 유지.

## 아키텍처

```
Agent (진입점, ~240줄)
  └─ OrchestratorAgent (최상위 조율)
       ├─ KeywordAgent     (키워드 추출 + 의도 분류 + 파라미터 매핑)
       ├─ RouterAgent      (실행 계획 수립 + 도구 순서 결정)
       ├─ PatentAgent      (KIPRIS Plus 특허 검색)
       ├─ CollectorAgent   (OpenAI tool-calling 루프 + 결과 수집)
       └─ SynthesizerAgent (LLM 기반 최종 답변 요약/생성)
```

## 변경 파일 목록

### 신규 생성
| 파일 | 역할 |
|------|------|
| `src/model/struct/agent/agents/__init__.py` | 패키지 초기화 |
| `src/model/struct/agent/agents/base_agent.py` | 서브 에이전트 공통 인터페이스 |
| `src/model/struct/agent/agents/keyword_agent.py` | 키워드 추출 + 의도 분류 + 파라미터 매핑 |
| `src/model/struct/agent/agents/router_agent.py` | 실행 계획 수립 + 도구 추천 |
| `src/model/struct/agent/agents/collector_agent.py` | OpenAI tool-calling 루프 + 근거 수집 |
| `src/model/struct/agent/agents/patent_agent.py` | KIPRIS Plus API 특허 검색 |
| `src/model/struct/agent/agents/synthesizer_agent.py` | LLM 기반 최종 답변 생성 |
| `src/model/struct/agent/agents/orchestrator_agent.py` | 최상위 조율 에이전트 |

### 변경
| 파일 | 변경 내용 |
|------|----------|
| `src/model/struct/agent.py` | 3541줄 → ~240줄로 슬림화. OrchestratorAgent에 위임하는 진입점 래퍼로 변경. 기존 인터페이스(run, get_tools, get_history) 유지. |

### 백업
| 파일 | 내용 |
|------|------|
| `src/model/struct/agent.py.bak` | 리팩토링 전 원본 (3541줄) |

## 핵심 설계 결정

1. **동적 모듈 로드**: WIZ `exec()` 환경 호환을 위해 `importlib.util.spec_from_file_location`으로 서브 에이전트를 순차 로드
2. **상대 import 폴백**: `try: from .base_agent import ... except: from base_agent import ...` 패턴으로 패키지/스크립트 양쪽 호환
3. **SSE 이벤트 100% 호환**: orchestration, pipeline, tool_use, tool_result, text, quality, evidence_items, done 이벤트 타입 모두 유지
4. **특허 검색 통합**: PatentAgent가 KIPRIS Plus API를 직접 호출하여 특허 관련 질의 자동 감지 및 결과 수집
5. **LLM 최종 요약**: SynthesizerAgent가 페이지 결과 + 문헌 + 특허를 모두 읽고 LLM으로 요약/정리하여 최종 답변 생성

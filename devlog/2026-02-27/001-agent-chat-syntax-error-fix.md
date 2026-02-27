# AI Agent 챗봇 응답 미반환 버그 수정

- **ID**: 001
- **날짜**: 2026-02-27
- **유형**: 버그 수정

## 작업 요약
AI 어시스턴트 챗봇에 질문을 보내면 답변이 돌아오지 않는 문제를 수정했다. 원인은 `config/season.py`의 OpenAI API 키 문자열이 줄바꿈 문자를 포함하여 Python SyntaxError가 발생, config 로드 실패로 500 Internal Server Error가 반환되던 것이었다.

## 변경 파일 목록

### Config
| 파일 | 변경 내용 |
|------|----------|
| `config/season.py` | API 키 문자열의 줄바꿈 제거 — 한 줄로 정상화 (SyntaxError 해결) |

### Agent Core
| 파일 | 변경 내용 |
|------|----------|
| `src/model/struct/agent.py` | `getattr` 기본값에서 하드코딩된 API 키 제거 → 빈 문자열 `""` 로 변경 (보안 개선) |

## 원인 분석
- `config/season.py` 6행의 `openai_api_key = "sk-proj-...` 문자열이 줄바꿈을 포함하여 7행에 닫는 따옴표 `"`가 별도 줄에 위치
- Python의 `"..."` 문자열은 줄바꿈을 허용하지 않으므로 `SyntaxError: unterminated string literal (detected at line 6)` 발생
- `wiz.config("season")` 호출 시 config 로드 실패 → Agent 생성 실패 → 500 Internal Server Error 반환
- 프론트엔드는 SSE 응답을 기다리지만 서버에서 500 에러만 반환되어 사용자에게는 "답변이 안 옴"으로 체감

## 검증 결과
- `agent_tools` API: 17개 도구 정상 반환 (code 200)
- `agent_chat` SSE: "hello" 메시지에 대해 정상 응답 + done + history 이벤트 수신 확인

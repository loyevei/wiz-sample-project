# OpenAI tool_call 히스토리 정합성 복구

- **ID**: 010
- **날짜**: 2026-03-24
- **유형**: 버그 수정

## 작업 요약
플로팅 챗봇 최종답변 단계에서 OpenAI Chat Completions가 `assistant`의 `tool_calls` 뒤에 대응되는 `tool` 메시지가 없다고 400 오류를 반환하던 문제를 수정했다.
대화 이력 복원 시 깨진 tool-call 블록을 정리하는 sanitizer를 추가하고, 실제 LLM 호출 직전에도 동일한 정합성 보정을 다시 적용해 중간 이력 손상에도 안전하게 동작하도록 보강했다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - `_sanitize_openai_history()` helper 추가
  - history 복원 시 assistant `tool_calls`와 대응 `tool_call_id`를 검증해 끊긴 블록 제거
  - LLM API 호출 직전에도 메시지 배열을 다시 보정해 400 invalid_request_error 재발 방지
- `.github/task/todo.md`
  - 이번 작업 완료 후 다음 작업 번호 템플릿으로 갱신
- `devlog.md`
  - 2026-03-24 작업 인덱스 010 추가

## 검증
- `wiz project build --project=main` 성공
- `src/model/struct/agent.py` 정적 오류 없음

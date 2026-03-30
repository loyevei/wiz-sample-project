# 중간결론 선표시 후 최종답변 교체 UX 도입

- **ID**: 018
- **날짜**: 2026-03-23
- **유형**: 기능 추가

## 작업 요약
플로팅 챗봇의 체감 응답 속도를 높이기 위해, 도구 실행 중에도 짧은 한국어 중간결론을 먼저 표시하고 최종 verification 답변이 오면 그 내용으로 교체하는 흐름을 추가했다.
이제 사용자는 공백 시간을 덜 느끼고, 초기 요약을 본 뒤 최종본으로 자연스럽게 전환되는 응답 UX를 경험할 수 있다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - `_build_quick_preview_answer()`를 추가해 page result 또는 tool result 기반의 짧은 한국어 preview 답변 생성
  - run loop에 preview 전송 상태를 관리하는 `_preview_emitted` 플래그 추가
  - tool 실행 중 첫 의미 있는 결과가 나오면 `text(stage=preview)` 이벤트를 먼저 전송
  - 최종본은 `text(stage=verification)`으로 명시해 프론트가 교체 처리할 수 있게 정리
- `src/app/component.chat.floating/view.ts`
  - `text(stage=preview)`는 임시 답변으로 표시
  - `text(stage=verification)` 또는 verification quality 이후 text는 최종답변으로 기존 내용을 교체
  - trace 설명을 preview 단계에 맞게 조정

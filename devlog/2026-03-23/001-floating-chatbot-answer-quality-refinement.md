# 플로팅 챗봇 최종답변 품질 개선

- **ID**: 001
- **날짜**: 2026-03-23
- **유형**: 기능 추가

## 작업 요약
플로팅 챗봇의 최종 답변이 짧게 끝나는 문제를 줄이기 위해, 검색 근거뿐 아니라 도구 실행 결과와 페이지 이동 파라미터까지 함께 읽어 OpenAI로 한글 최종 답변을 재정리하도록 보강했다.
또한 플로팅 챗 UI에서 검증된 최종 답변이 초안 뒤에 덧붙지 않고 우선 노출되도록 스트리밍 처리 흐름을 조정했다.

## 변경 파일 목록
- `src/model/struct/agent.py`
  - 검색 근거 외에 도구 결과와 마지막 네비게이션 정보를 별도 bank로 수집하도록 확장
  - OpenAI 최종 정제 프롬프트에 tool output, navigation context, query/params를 함께 주입
  - 초안이 비거나 짧은 경우에도 한글 구조화 답변을 재생성하도록 refinement 조건 강화
- `src/app/component.chat.floating/view.ts`
  - 새 질의 시작 시 이전 pending navigation 초기화
  - verification 단계의 최종 텍스트 이벤트는 기존 초안에 append하지 않고 교체하도록 수정
- `src/app/page.agent/view.ts`
  - 페이지형 에이전트도 verification 단계에서 최종 텍스트를 우선 반영하도록 동일 패턴 적용

## 검증
- `cd /opt/app/project/main && wiz project build --project=main`
- 서버 재시작 없이 normal build 완료

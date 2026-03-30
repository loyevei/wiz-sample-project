# 플로팅 챗봇 최종답변 재구성 및 사고과정 단일 섹션화

- **ID**: 008
- **날짜**: 2026-03-23
- **유형**: 기능 추가

## 작업 요약
플로팅 챗봇의 분리된 오케스트레이션 상태/현재 단계/실행 사고 로그/실행 계획 카드를 하나의 `답변 생성 과정` 섹션으로 통합했다.
동시에 `read_page_results` 기반 페이지 결과를 우선 근거로 사용하는 한국어 최종답변 재구성 로직을 강화하고, LLM 응답이 약할 때도 페이지 결과 기반 구조화 답변으로 fallback 되도록 보강했다.

## 변경 파일 목록
- `src/app/component.chat.floating/view.pug`
  - 분리된 상태/로그/계획 카드 제거
  - `답변 생성 과정` 단일 섹션으로 통합
  - 페이지 이동 액션은 별도 카드로 유지
- `src/app/component.chat.floating/view.ts`
  - 질문/실행계획/도구/페이지결과/근거/품질검증을 하나의 journey 목록으로 합성하는 헬퍼 추가
  - 초기 안내 문구를 페이지 결과 기반 한국어 답변 흐름에 맞게 조정
- `src/model/struct/agent.py`
  - `read_page_results` 결과를 바탕으로 한국어 구조화 답변 fallback 추가
  - refinement 실패 또는 응답 품질이 약한 경우에도 `핵심 결론 / 근거 / 한계 / 다음 액션` 형식 유지
- `.github/task/todo.md`
  - 이번 작업 TODO 등록 후 완료 처리 대상 정리

## 검증
- `cd /opt/app/project/main && wiz project build --project=main`

# 플로팅 챗봇 실행 계획 원문 노출 및 페이지 결과 우선 답변 강화

- **ID**: 007
- **날짜**: 2026-03-23
- **유형**: 기능 추가

## 작업 요약
플로팅 챗봇 UI에서 기존의 추상적인 파이프라인 카드 블록을 제거하고, 오케스트레이터가 계산한 실제 실행 계획을 텍스트 중심으로 직접 노출하도록 재구성했다.
또한 `read_page_results` 결과를 별도 페이지 결과 컨텍스트로 수집해 최종답변 재작성 시 1차 근거로 우선 사용하도록 강화했다.

## 변경 파일 목록
- `src/app/component.chat.floating/view.pug`
  - `최종 답변 구성 요소` 파이프라인 카드 제거
  - `실제 실행 계획` 섹션 추가
  - 분류/목표 페이지/키워드/도구 순서/파라미터 매핑/실행 계획 원문/페이지 결과 추출/페이지 이동 계획을 텍스트로 표시
- `src/app/component.chat.floating/view.ts`
  - `executionPlan` 상태 추가 및 SSE 오케스트레이션/도구 이벤트와 동기화
  - `read_page_results`, `navigate_to_page` 입력/결과를 실행 계획과 연결
  - 파이프라인 카드 상태 관리 로직 제거
- `src/model/struct/agent.py`
  - 오케스트레이션 이벤트에 `execution_plan` 구조 추가
  - `read_page_results` 결과를 `_page_result_bank`에 보관
  - 최종답변 refinement에서 페이지 결과를 1차 근거로 우선 사용하도록 프롬프트/합성 포인트 강화

## 검증
- `cd /opt/app/project/main && wiz project build --project=main`

# 플로팅 챗봇과 페이지 간 Milvus 컬렉션 동기화

- **ID**: 001
- **날짜**: 2026-03-19
- **유형**: 기능 추가

## 작업 요약
플로팅 챗봇에서 선택한 Milvus 컬렉션을 로컬 저장소와 페이지 이동 쿼리로 함께 전달하도록 수정했다.
Research, Prediction, Diagnosis, Theory 페이지는 저장된 컬렉션을 우선 반영하고 사용자가 페이지에서 변경한 선택도 다시 저장해 플로팅 챗봇과 동일 상태를 유지한다.

## 변경 파일 목록
- `src/app/component.chat.floating/view.ts`
  - 선택 컬렉션을 localStorage에 저장/복원하도록 추가
  - `navigate_to_page` 결과에서 collection을 읽어 페이지 이동 queryParams에 반영
  - 답변 텍스트가 비어 있을 때 에이전트 요약 fallback 생성
- `src/app/page.research/view.ts`
  - 저장된 컬렉션 우선 적용 및 변경 시 재저장
- `src/app/page.prediction/view.ts`
  - 저장된 컬렉션 우선 적용 및 변경 시 재저장
- `src/app/page.diagnosis/view.ts`
  - 저장된 컬렉션 우선 적용 및 변경 시 재저장
- `src/app/page.theory/view.ts`
  - 저장된 컬렉션 우선 적용 및 변경 시 재저장
- `build/src/app/component.chat.floating/component.chat.floating.component.ts`
- `build/src/app/page.research/page.research.component.ts`
- `build/src/app/page.prediction/page.prediction.component.ts`
- `build/src/app/page.diagnosis/page.diagnosis.component.ts`
- `build/src/app/page.theory/page.theory.component.ts`
  - 빌드 API 복사 실패를 우회하기 위해 최신 변경을 수동 동기화

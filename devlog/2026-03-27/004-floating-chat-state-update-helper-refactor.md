# 플로팅 챗봇 상태 갱신 구조 리팩토링

- **ID**: 004
- **날짜**: 2026-03-27
- **유형**: 리팩토링

## 작업 요약
플로팅 챗봇의 SSE 이벤트 처리 과정에서 `previewContent`, `pageResultCard`, `navigationCard`를 갱신하는 로직이 여러 함수에 중복되어 있어 공용 헬퍼로 통합했다.
동작은 유지하면서 카드 상태 패치, 프리뷰 텍스트 갱신, navigate payload 반영 경로를 일원화해 이후 기능 확장 시 결합도를 낮추고 수정 범위를 줄였다.

## 변경 파일 목록
- `src/app/component.chat.floating/view.ts`
  - `updatePreviewContent`, `patchPageResultCard`, `patchNavigationCard`, `applyNavigationPayload` 헬퍼 추가
  - `handleToolResult`, `applyToolUseTrace`, `applyToolResultTrace`, `applyQualityEvent`, `applyPipelineEvent`, `applyOrchestrationEvent`, `finalizeTrace`에서 중복 상태 갱신 로직 제거 및 헬퍼 사용으로 정리

# 플로팅 챗봇 /embedding 컬렉션 연결 및 버튼 노출 복구

- **ID**: 002
- **날짜**: 2026-03-18
- **유형**: 버그 수정

## 작업 요약
플로팅 챗봇에서 DB 선택 화면이 비어 보이던 원인을 확인하고, 챗봇이 자체 컬렉션 API 대신 `/embedding` 페이지에서 사용 중인 검증된 `collections` API를 직접 호출하도록 변경했다.
서버 재시작 없이 normal build 및 프런트 번들 반영을 수행해, 구축된 Milvus 컬렉션들이 챗봇 시작 시 버튼 형태로 표시되도록 복구했다.

## 변경 파일 목록
- `src/app/component.chat.floating/view.ts`
  - 컬렉션 로딩을 `/wiz/api/page.embedding/collections` 경로로 연결
  - 실패 시 기존 로컬 `collections` API로 fallback 하도록 보강
  - 컬렉션 목록을 문서 수 기준으로 정렬하고 선택 상태 보정
- `bundle/www/main.js`
  - 최신 프런트 번들 반영
- `.github/task/todo.md`
  - 작업 항목 등록 및 완료 후 다음 템플릿 번호로 정리
- `.github/task/worked/FN-20260318-0002.md`
  - 작업 완료 아카이브 작성

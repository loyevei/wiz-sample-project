# 플로팅 챗봇 DB 버튼 UI 및 Research 3기능 점검/빌드 반영

- **ID**: 001
- **날짜**: 2026-03-18
- **유형**: 버그 수정

## 작업 요약
플로팅 챗봇의 컬렉션 선택 UI가 버튼 형태로 동작하는지 확인하고, Research 페이지의 논문 추천·제안서 생성·특허 검색 API를 실제 런타임에서 재검증했다.
서버 재시작 없이 normal build와 프런트 번들 반영을 수행하고, 세 기능이 모두 200 응답으로 동작함을 확인했다.

## 변경 파일 목록
- `src/app/component.chat.floating/view.pug`
  - DB 컬렉션 선택 화면이 pill/button 형태로 구성되어 있음을 확인
- `src/app/page.research/api.py`
  - 추천/제안서/특허 API가 Milvus 검색 파라미터와 필드 구성을 기준으로 정상 동작함을 재검증
- `build/dist/build/main.js`
  - normal build 후 프런트 번들 재생성
- `bundle/www/main.js`
  - 최신 프런트 번들을 런타임 경로에 반영
- `.github/task/todo.md`
  - 오늘 작업 항목 등록 후 완료 처리에 따라 다음 템플릿 번호로 정리
- `.github/task/worked/FN-20260318-0001.md`
  - 완료 작업 아카이브 작성

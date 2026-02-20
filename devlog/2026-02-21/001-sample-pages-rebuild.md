# 샘플 Page 앱 전면 교체

- **ID**: 001
- **날짜**: 2026-02-21
- **유형**: 리팩토링

## 작업 요약
기존 인프라 관리 전용 page 앱 14개를 전부 삭제하고, 일반적인 서비스 구조를 참고할 수 있는 샘플 page 앱 6개를 생성했다. 사이드바 내비게이션과 controller도 함께 업데이트했다.

## 삭제된 앱
- page.access, page.main, page.mypage
- page.project, page.project.item, page.deploy
- page.admin.deploy, page.admin.images, page.admin.images.item
- page.admin.project, page.admin.project.item
- page.admin.template, page.admin.template.item, page.admin.users

## 생성된 앱 (샘플 패턴별)

| 앱 | viewuri | 패턴 | 설명 |
|----|---------|------|------|
| page.access | /access | 로그인 폼 | layout.empty, 이메일/비밀번호 인증 |
| page.dashboard | /dashboard | 대시보드 | 통계 카드, 최근 활동, 바로가기 |
| page.posts | /posts | 목록 (검색/필터/페이지네이션) | 카테고리 필터 태그, 테이블, 디바운싱 검색 |
| page.posts.item | /posts/:id/:tab? | 상세 (탭 전환) | view/edit/settings 탭, NavigationEnd 구독, 404 처리 |
| page.members | /members | 카드 그리드 + 모달 | 역할 필터, 초대 모달, 그리드 레이아웃 |
| page.mypage | /mypage | 프로필 폼 | 개인정보 수정, 비밀번호 변경 |

## 변경 파일 목록

### App (신규 생성)
- `src/app/page.access/` — 로그인 (app.json, view.ts, view.pug, api.py)
- `src/app/page.dashboard/` — 대시보드 (app.json, view.ts, view.pug, api.py)
- `src/app/page.posts/` — 게시물 목록 (app.json, view.ts, view.pug, api.py)
- `src/app/page.posts.item/` — 게시물 상세 (app.json, view.ts, view.pug, api.py)
- `src/app/page.members/` — 멤버 관리 (app.json, view.ts, view.pug, api.py)
- `src/app/page.mypage/` — 내 프로필 (app.json, view.ts, view.pug, api.py)

### Component (수정)
- `src/app/component.nav.sidebar/view.pug` — 로고를 아이콘+텍스트로 변경, 메뉴 항목을 Dashboard/게시물/멤버로 교체

### Controller (수정)
- `src/controller/user.py` — portal/infra/struct 참조 제거, TODO 주석으로 대체

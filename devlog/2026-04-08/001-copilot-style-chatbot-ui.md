# VS Code Copilot 스타일 챗봇 UI 전면 개편

- **ID**: 001
- **날짜**: 2026-04-08
- **유형**: UI 리팩토링

## 작업 요약
플로팅 AI 에이전트 챗봇의 UI를 VS Code Copilot 채팅 스타일로 전면 개편했다. 기존의 카드 기반 heavy UI(journey 애니메이션, 컬러풀한 fuchsia 그라데이션, 다단계 progress bar)를 제거하고, Copilot처럼 미니멀하고 깔끔한 대화형 인터페이스로 교체했다.

## 핵심 변경 사항

### 1. 어시스턴트 메시지 레이아웃
- **Before**: `flex justify-start` + 단일 콘텐츠 div (max-w-[94%])
- **After**: `flex gap-2.5` + 아바타(6x6 violet 아이콘) + 콘텐츠 div
- 각 어시스턴트 메시지에 봇 아바타 아이콘 표시

### 2. Thinking 섹션 (핵심 변경)
- **Before**: `overflow-hidden rounded-3xl` 카드 안에 progress bar, 스테이지 칩, journey reveal 애니메이션, 현재 단계 하이라이트, 숨겨진 단계 카운터, 예정 단계 프리뷰, 다음 카드 미리보기 등 복잡한 UI
- **After**: Copilot 스타일 `Thinking...` 토글 버튼 + 스피너/체크마크 + 접을 수 있는 단순 스텝 리스트 (✓/◔/○/✕/↷ 상태 아이콘)

### 3. 도구 호출 표시
- **Before**: trace 카드 내부에 숨김
- **After**: 인라인 칩으로 `Used {도구명}` 형태 표시 (Copilot의 "Used search_papers" 스타일)

### 4. 네비게이션/페이지 결과 카드
- **Before**: 컬러풀한 gradient 카드 (cyan/violet 배경, 로딩 스켈레톤, 이모지 헤더)
- **After**: 심플한 `rounded-lg border-slate-200 bg-slate-50` 카드, 미니멀한 레이아웃

### 5. 답변 영역
- **Before**: 카드 래퍼 (rounded-3xl border, 🤖 아이콘 + "최종 답변" 헤더)
- **After**: 카드 래퍼 없이 직접 마크다운 콘텐츠 표시 (깔끔한 flow)

### 6. 품질 분석/근거 문헌
- **Before**: 에메랄드/앰버 컬러 대형 카드
- **After**: 품질은 인라인 배지, 근거는 미니멀 아코디언

### 7. 액션 바
- 답변 하단에 작은 "복사" 버튼 추가

### 8. 헤더/입력 영역
- **Before**: `from-slate-950 via-violet-950 to-fuchsia-950` 그라데이션, 12x12 아바타, subtitle 표시
- **After**: `bg-slate-900` 단색, 7x7 아바타, 컴팩트한 레이아웃
- 입력 영역: 로봇 아바타 제거, violet 색조로 통일

### 9. 플로팅 버튼
- **Before**: 16x16 복잡한 다층 구조 (그라데이션 배경 + radial gradient + text)
- **After**: 14x14 심플한 라운드 버튼

### 10. SCSS
- journey 관련 키프레임 애니메이션 5개 제거 (journeyReveal, journeyGlow, cardSlideUp, skeletonShimmer)
- `.journey-reveal`, `.journey-reveal-current` 클래스 제거
- 스크롤바 색상을 slate로 변경 (fuchsia/purple → neutral)
- `.copilot-thinking` 클래스 추가

## 변경 파일 목록

### UI (view.pug)
- `src/app/component.chat.floating/view.pug` — 전면 재작성 (232행 → 196행)

### 로직 (view.ts)
- `src/app/component.chat.floating/view.ts` — `getUsedToolNames()` 메서드 추가

### 스타일 (view.scss)
- `src/app/component.chat.floating/view.scss` — journey 애니메이션 제거, Copilot 스타일 적용 (307행 → 약 210행)

## 보존된 기능
- 페이지 이동 (navigate) 기능 유지
- 인자값 입력 후 결과 표시 기능 유지
- 마크다운 렌더링 (코드 블록, 테이블 등) 유지
- 근거 문헌 아코디언 유지
- 답변 복사 기능 유지
- 컬렉션 선택/변경 유지
- SSE 스트리밍 + 타이핑 애니메이션 유지

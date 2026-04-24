# Angular 번들 빌드 실패 수정 (marked 의존성 누락)

- **ID**: 001
- **날짜**: 2026-04-10
- **유형**: 버그 수정

## 작업 요약
사이드바 챗봇(`component.chat.sidebar`)에서 최종 답변이 표시되지 않는 문제의 근본 원인을 진단하고 수정했다. 백엔드 SSE 스트림은 정상 동작하고 있었으나, Angular 번들이 구버전 코드로 제공되고 있었으며, 이는 `marked` 패키지가 `src/angular/package.json`에 누락되어 esbuild 컴파일이 실패했기 때문이었다.

## 진단 과정
1. **curl SSE 테스트**: `text` 이벤트에 실제 한국어 답변이 포함되어 백엔드 정상 확인
2. **번들 분석**: `bundle/www/main.*.js`에서 `startTypewriter`, `shouldRenderAnswerCard`, `chat-markdown-body` 등 신규 메서드가 0건 — 구버전 번들 확인
3. **클린 빌드 시도**: esbuild에서 `Could not resolve "marked"` 에러 발생 — 컴파일 실패 확인
4. **원인**: `src/angular/package.json`에 `marked` 의존성이 누락되어 클린 빌드 시 `node_modules`에 설치되지 않음

## 변경 파일 목록

### Angular 빌드 설정
- **`src/angular/package.json`**: `marked` (^17.0.4), `katex` (^0.16.38) 의존성 추가

### Before
```json
"jquery": "^3.6.1",
"moment": "^2.30.1",
```

### After
```json
"jquery": "^3.6.1",
"katex": "^0.16.38",
"marked": "^17.0.4",
"moment": "^2.30.1",
```

## 검증
- 클린 빌드 성공: `EsBuild complete in 172ms`
- 새 번들 검증: `startTypewriter`(2), `shouldRenderAnswerCard`(6), `chat-markdown-body`(96), `typingActive`(31) 포함 확인
- API 테스트: `text` 이벤트에 "안녕하세요! 플라즈마 과학 및 엔지니어링 분야의..." 답변 정상 수신

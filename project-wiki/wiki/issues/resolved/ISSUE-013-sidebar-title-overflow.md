---
name: ISSUE-013 사이드바 대화 목록 제목이 오른쪽으로 overflow
description: 자동 제목(ISSUE 별건 후속) 백필로 긴 한국어 제목이 사이드바를 넘쳐 오른쪽으로 overflow. flex item의 min-width:auto = min-content + Radix ScrollArea viewport의 display:table이 truncate를 깨뜨림. min-w-0 추가 + ScrollArea를 일반 div로 교체해 해결.
type: issue
---

# ISSUE-013: 사이드바 대화 목록 제목 오른쪽 overflow

**상태**: resolved · 2026-04-30
**발생일**: 2026-04-30
**해결일**: 2026-04-30
**관련 기능**: NextJS 사이드바(ADR-030)
**관련 코드**:
- [web/components/sidebar.tsx](../../../../web/components/sidebar.tsx) — root flex container + Radix ScrollArea 교체

---

## 증상

자동 제목 생성(첫 user 메시지 → conversation.title)이 도입되면서 긴 한국어 제목이 사이드바 너비(256px = `w-64`)를 넘쳐 오른쪽으로 밀려남. truncate 클래스가 동작하지 않아 사이드바 자체가 가로로 확장되어 보였음.

Playwright 측정 (수정 전):
- aside width: 256px (정상)
- 내부 flex root div: **330px** (overflow!)
- ul: **315px**

## 원인 분석

두 단계 원인:

1. **사이드바 root가 flex item인데 `min-width: auto`로 평가됨**
   - `<aside className="hidden md:flex w-64 shrink-0">` — 부모는 256px width 고정, flex-row
   - 자식 `<div className="flex flex-1 min-h-0 flex-col">` — flex-1만 있고 `min-w-0` 부재
   - CSS 명세상 flex item의 `min-width: auto`는 `min-content`로 평가 → 자식 콘텐츠(긴 제목)의 intrinsic min-width가 256px보다 크면 부모를 뚫고 확장
   - flex-shrink가 작동하려면 `min-width: 0` 명시 필요

2. **Radix ScrollArea viewport가 `display: table` 류로 콘텐츠 너비에 맞춰 커짐**
   - shadcn/ui의 ScrollArea는 Radix 기반인데 내부 viewport가 `min-width: 100%; display: table` 패턴을 사용해 자식의 intrinsic 너비를 측정
   - 자식 ul/li의 `truncate` 체인이 부모 너비 제약을 받지 못함

## 해결 방법

`web/components/sidebar.tsx`:

1. 사이드바 root div에 `min-w-0` 추가:
   ```tsx
   <div className="flex flex-1 min-h-0 min-w-0 flex-col">
   ```
2. Radix `ScrollArea`를 일반 `<div className="flex-1 overflow-y-auto min-w-0">`로 교체. 사이드바에서 custom 스크롤바 styling은 사소하고, 정확한 truncate 동작이 우선

기존 button/li/ul 내부 `flex-1 min-w-0` + `truncate` 체인은 그대로 유지 (이제 부모 제약이 제대로 전파됨).

## 검증

Playwright 측정 (수정 후):
- aside width: 256px
- aside.scrollWidth: **255px** (overflow 0 ✓)
- ul width: 240px (제대로 들어감)
- 첫 button width: 224px
- label 영역 width: 208px / scrollWidth(자연 텍스트): 211px → **truncated: true** ✓

"종말일기_Z의 주요 내용은 무엇인가요?" 같은 60자 제목이 정상적으로 `…`로 잘림.

## 재발 방지

**flex item에 `min-w-0` (또는 `min-h-0`) 명시는 truncate/overflow 패턴의 필수 전제**. Tailwind `flex-1`만 추가하면 `min-width: auto`라 의도와 어긋남. 새 사이드바·패널·드로어 추가 시 체크리스트로 둘 만한 항목.

**Radix ScrollArea**는 가로 truncate가 필요한 컨테이너에는 부적합. 세로만 스크롤하면 충분한 영역엔 일반 `overflow-y-auto`로 가는 게 단순·안전.

**관련**: ISSUE-012(같은 세션의 UX 폴리시 묶음), 대화 제목 자동 생성 변경(같은 0.29.0 릴리즈)

---

## 후속 폴리시 (0.30.1, 2026-04-30)

가로 overflow 본 이슈는 해결됐지만, 호버 시 나타나는 trash 아이콘과 truncate 말줄임표가 시각적으로 너무 가깝다는 사용자 보고. 항목 버튼이 `px-2` 좌우 동일 패딩이라 절대 위치 trash 아이콘 자리(약 24px)가 텍스트 영역과 겹쳐 truncate 끝점에 아이콘이 바로 붙음.

**수정**: `web/components/sidebar.tsx:65-68` — `px-2` → `pl-2 pr-8`. 우측 32px를 항상 예약해 호버 여부와 무관하게 일정한 텍스트 영역 확보. `group-hover:pr-8` 방식은 호버 진입 시 truncate 끝점이 시각적으로 점프해 채택 안 함.

재발 방지 항목 보강: **절대 위치 액션 아이콘이 호버 시 노출되는 패턴**은, 비호버 상태에서도 아이콘 자리만큼 컨테이너 패딩을 예약해 둘 것. 호버 토글 패딩은 레이아웃 시프트 + truncate 끝점 점프를 유발.

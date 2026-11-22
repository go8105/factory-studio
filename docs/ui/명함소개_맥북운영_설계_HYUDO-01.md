# HYUDO-01 — 명함 소개 페이지(www.hyudo.kr)와 맥북 운영 전환 설계

2026-11-22 · Claude Code · **설계 문서. 제품 코드·DB 변경 없음.**

사용자 요청: 명함 QR(`www.hyudo.kr`)로 들어온 사람이 "어떤 사람인지" 보는 이력서형 소개 화면. 학교·자격증·경력·수상·휴대용 비누 그라인더를 보여 준다. `hugh-d.com`은 삭제했으니 EIP는 `eip.hyudo.kr`로 옮긴다. Vultr 서버도 내렸으니 맥북에서 운영한다.

선행 설계: [ABOUT-01 자기소개·기술 노트](자기소개_기술노트_설계_ABOUT-01.md) — 콘텐츠(`content/about/profile.json`)와 `/about` 화면은 그대로 쓴다. 이 문서는 **모바일 명함 화면, 도메인, 운영 위치**만 바꾼다.

---

> **HYUDO-03 반영(2026-11-22):** 사용자가 Figma Make로 화면을 만들어 넘겼다(명함 앞뒤면과 같은 쪽빛·샴페인 골드 `#B39B6E`·携渡 디자인). 그 코드를 `card/`에 그대로 옮겼다(3-1의 profile.json 재사용·별도 진입점 안 대신). **EIP `/about`과 `content/about/profile.json`은 폐지**하고 `eip.hyudo.kr/about`은 www로 301. 비누 이미지는 v3 STL 9개를 Blender로 조립한 스튜디오 렌더(실물 사진 오면 `card/public/images/soap-grinder.jpg` 교체).

## 1. 확정 결정 (2026-11-22 사용자)

| # | 결정 | 이전 결정과의 관계 |
|---|---|---|
| H1 | **모바일 우선(390px).** PC는 같은 화면을 가운데 정렬로 넓힌다 | ABOUT-01 "PC 1440 전용"을 명함 화면에 한해 뒤집는다. EIP `/about`은 유지 |
| H2 | **www와 eip 모두 맥북에서 운영**한다. Cloudflare Pages 분리안은 쓰지 않는다 | FS-022(Vultr) 대체 |
| H3 | 비누 그라인더는 **홍보용 사진 + 이름 + 한 줄 소개만** 공개한다(사진 2026-11-23 도착 예정) | CAD-03 "관리자 비누 POC 비공개"는 유지. 3D·도면·연구노트는 공개하지 않는다 |
| H4 | **예전 운영 DB는 복구하지 않는다.** 시드(합성 데이터)로 새로 시작한다 | 2026-11-22 Vultr 콘솔 확인: 인스턴스·스냅샷·블록 스토리지 모두 없음 |
| H5 | 피그마 시안은 **사용자가 피그마 AI로 직접** 만든다(아래 6장 프롬프트) | Figma MCP 미인증 |

---

## 2. 운영 구조

```
명함 QR / 브라우저
   │ https
Cloudflare (hyudo.kr 영역, 네임서버 이미 연결됨)
   │ ── hyudo.kr → 301 www.hyudo.kr (Cloudflare 리다이렉트 규칙)
   │ Cloudflare Tunnel (공유기 포트 개방·공인 IP 불필요)
맥북 M1 Pro ── cloudflared (launchd 상시 실행)
   ├─ www.hyudo.kr → localhost:8080  명함 페이지 정적 파일
   └─ eip.hyudo.kr → localhost:8080  frontend/dist + /api/ → uvicorn 127.0.0.1:8021
                     Postgres Docker 127.0.0.1:55432 (기존 factory-studio-db-1)
```

- **정적 파일과 `/api` 분기는 맥북의 Nginx(Homebrew) 한 곳**에서 한다. FS-022 서버 블록을 거의 그대로 옮기고, TLS는 Cloudflare가 끝내므로 맥북 Nginx는 `127.0.0.1:8080` 평문만 듣는다. cloudflared만으로는 정적 파일을 서빙할 수 없어서 Nginx가 필요하다.
- 외부에 열리는 포트는 **없다.** 터널은 맥북에서 밖으로 나가는 연결이다. Postgres·uvicorn·Nginx는 모두 127.0.0.1에만 바인딩한다.
- 백엔드 도메인 설정은 `FS_PUBLIC_ORIGIN=https://eip.hyudo.kr` 하나다(`backend/src/fs/core/security/config.py`). 코드에 `hugh-d.com`은 없다.

### 2-1. 상시 가동 조건

| 항목 | 상태 |
|---|---|
| 전원 연결 시 잠자기 | **확인함** — `pmset -g custom` AC: `sleep 0`, `disksleep 0`, `displaysleep 120` |
| 덮개 | 열어 둔다(외장 모니터 없이 닫으면 잠든다) |
| 배터리 | 상시 충전은 100% 유지 시 노화가 빠르다. 80% 충전 제한 권장(macOS 최적화 충전 또는 AlDente) |
| 재부팅 후 자동 복구 | cloudflared·Nginx·API를 launchd로 등록. Docker Desktop은 "로그인 시 시작" + 컨테이너 `restart: unless-stopped`. **macOS 업데이트 등으로 재부팅되면 로그인 전까지 Docker가 안 뜬다** — 자동 로그인 여부는 사용자 판단 |
| 꺼졌을 때 | 두 주소 모두 Cloudflare 오류 화면(530/1033). 명함 링크도 함께 멈춘다 — H2에서 감수하기로 함 |

---

## 3. 명함 페이지(www.hyudo.kr)

### 3-1. 구현 방식
- 콘텐츠는 **기존 `content/about/profile.json`**을 쓴다. 새로 필요한 필드만 추가한다: `education`(학력), `certificates`(자격, 현재 `education`에 섞여 있음), `product`(제목·한 줄·사진 경로·배지).
- 화면은 EIP 앱 번들과 분리한 **가벼운 별도 Vite 진입점**(`card.html`)으로 만든다. 명함 QR은 휴대폰 데이터로 열리므로 CAD/WASM이 섞인 EIP 번들을 받지 않게 한다. 기존 `About.tsx`의 섹션 컴포넌트를 재사용할 수 있으면 재사용한다.
- 서버 요청 0건(정적). 사진은 웹용으로 줄여(가로 1200px, WebP) 리포지토리에 둔다 — 홍보용으로 사용자가 넘겨준 사진만.

### 3-2. 섹션 순서 (위 → 아래)
1. 상단 바 `hyudo`
2. 히어로 — 프로필 사진(선택), 이름, 직함 "제조 IT 개발자 · 휴대용 비누 그라인더 메이커", 한 줄 소개, 버튼 [연락처 저장] [이메일]
3. **지금 만드는 것** — 비누 그라인더 사진 카드 + 한 줄 + 배지 "모두의 창업 1라운드 합격"
4. 숫자 3개 — 4년+ · 6곳 · 5개 모듈
5. 학력 — 한국방송통신대학교 컴퓨터과학과
6. 자격증 — 정보처리기사 필기 · SQLD · 리눅스마스터 2급 · 전산회계 2급
7. 경력 — 2곳 타임라인, 성과 한 줄씩
8. 수상 — 넷제로 스케일업상(2026.10)
9. Factory Studio 체험 → `eip.hyudo.kr`
10. 하단 — 이메일 · GitHub

### 3-3. 공개 원칙 (ABOUT-01 5장 유지)
- 전화번호·주소·생년 없음. **[연락처 저장]은 vCard(이름·이메일·웹 주소만)**로 만든다.
- 고객사 실명 없음. 비누 그라인더는 H3 범위만.

---

## 4. 도메인 이전 (eip.hugh-d.com → eip.hyudo.kr)

| 바꿀 곳 | 내용 |
|---|---|
| 맥북 `.env` | `FS_PUBLIC_ORIGIN=https://eip.hyudo.kr` |
| Cloudflare | 터널 공개 호스트 2개(www·eip), `hyudo.kr` → www 301 |
| `docs/agent/assets/about03/public-check.mjs` | 기본 URL `https://eip.hyudo.kr` |
| 배포 문서 | 새 맥북 운영 절차서(`docs/deploy/`)를 만들고 FS-022는 "폐기(Vultr 삭제)" 표시 |
| `tools/deploy.sh` | ssh 대상(Vultr)이 없어졌다. 맥북 로컬 배포 스크립트로 대체 |
| EIP 내 링크 | `/about`의 "만든 사람"·명함 페이지의 체험 링크를 새 주소로 |

- **과거 작업 기록(HANDOFF·progress·agent 결과 문서)의 `hugh-d.com`은 고치지 않는다.** 당시 사실이다.
- `hugh-D Company`(시드의 예시 회사명)는 도메인이 아니라 브랜드명이므로 이번 범위가 아니다.

---

## 5. 작업 나누기

| ID | 내용 | 선행 |
|---|---|---|
| HYUDO-02 | 맥북 운영: cloudflared 설치·터널, Nginx, launchd, 새 DB(시드)·관리자 계정, `FS_PUBLIC_ORIGIN`, 운영 절차서, 공개 확인 | 사용자 Cloudflare 로그인(브라우저) |
| HYUDO-03 | 명함 페이지 구현·배포(`card.html`, profile.json 필드, vCard, 사진) | 사용자 피그마 시안 + 비누 그라인더 사진 |
| HYUDO-04 | 도메인 문서·스크립트 정리(4장 표) | HYUDO-02 |

---

## 6. 피그마 AI 프롬프트 (사용자 직접 작성용)

사용자에게 대화로 전달한 원문(2026-11-22)을 그대로 둔다. 색·섹션은 3장과 AGENTS.md 7장 기준이다.

```text
모바일 자기소개 웹페이지 1장을 디자인해줘. 명함 QR을 휴대폰으로 스캔하면 열리는 화면이다.
[프레임] iPhone 390×844 기준, 세로로 길게 스크롤(약 390×2400). 한국어.
[톤] 차분하고 단정한 개인 포트폴리오. 화려한 그라데이션·일러스트·이모지 금지.
[색] 배경 #F7F7F6, 본문 #1A1C1E, 강조·버튼 #1F2D3D, 보조 글자 #6B6F73, 구분선 #E4E4E1.
[스타일] 단색 라인 아이콘, 그림자 최대 4%, 모서리 12px 카드, 저채도 회색 배지. Pretendard(없으면 Noto Sans KR). 좌우 여백 20px.
[섹션] 3-2의 1~10 순서. 사진 자리는 회색 박스. 전화번호·주소·생년 없음.
```

# HYUDO-02 맥북 운영 절차서 — eip.hyudo.kr · www.hyudo.kr

2026-11-22 · Claude Code. [FS-022 Vultr 절차서](배포절차_FS-022.md)를 대체한다(Vultr 서버 삭제, `hugh-d.com` 폐기). 설계는 [HYUDO-01](../ui/명함소개_맥북운영_설계_HYUDO-01.md).

## 0. 구성

```
방문자 ─https─ Cloudflare(hyudo.kr) ─Tunnel factory-studio-mac─ 맥북
  cloudflared (kr.hyudo.cloudflared) → Nginx 127.0.0.1:8080 (sh.brew.nginx)
     eip.hyudo.kr  → frontend/dist + /api/ → uvicorn 127.0.0.1:8021 (kr.hyudo.fs-api)
     www.hyudo.kr  → card/dist (명함 페이지, HYUDO-03)
     hyudo.kr → 301 www,  eip.hyudo.kr/about → 301 www (EIP 소개 화면은 HYUDO-03에서 폐지)
     그 외 이름 → 444(연결 끊음), http → https 301(X-Forwarded-Proto 기준)
  Postgres: Colima(profile factory-studio) 컨테이너 factory-studio-prod-db-1, 127.0.0.1:55442, restart unless-stopped
  게스트 정리: kr.hyudo.fs-cleanup 900초마다
```

| 위치 | 내용 |
|---|---|
| `~/projects/factory-studio-prod` | 운영 전용 worktree(**detached HEAD**). 개발 폴더와 분리 |
| `~/projects/factory-studio-prod/.env` | 운영 비밀값(600, Git 제외). `FS_PUBLIC_ORIGIN=https://eip.hyudo.kr`, `POSTGRES_PORT=55442`, PUBLIC_DEMO 모드(기본) |
| `~/Library/LaunchAgents/kr.hyudo.*.plist` | api · cleanup · cloudflared · colima |
| `/opt/homebrew/etc/nginx/nginx.conf` | 운영 Nginx(원본은 `nginx.conf.brew-default`), `fs_proxy_params` |
| `~/.cloudflared/` | `cert.pem`, 터널 자격 증명 JSON, `config.yml`(인그레스 3개) |
| `~/Library/Logs/factory-studio/` | 각 서비스 로그 |

- 운영 DB는 **개발 DB(`factory-studio-db-1`, 55432)와 다른 컨테이너·볼륨**이다. 개발 폴더에서 `docker-compose down -v`를 해도 운영은 지워지지 않는다. 운영 쪽은 반드시 `-p factory-studio-prod`를 붙인다.
- 외부로 열린 포트는 없다. 모든 서비스가 127.0.0.1에만 바인딩된다.

## 1. 상시 가동 조건

- 전원 연결 · 덮개 열기. `pmset -g custom`의 AC에 `sleep 0`, `disksleep 0`(2026-11-22 확인).
- 재부팅 후 **사용자 로그인**이 되어야 LaunchAgent(Colima·API·Nginx·터널)가 뜬다. 자동 로그인을 켜지 않으면 로그인 전까지 사이트가 멈춘다.
- 배터리 상시 충전: 80% 제한 권장.

## 2. 상태 확인

```bash
launchctl list | grep -E "hyudo|nginx"
docker ps --filter name=prod
curl -s -o /dev/null -w '%{http_code}\n' https://eip.hyudo.kr/api/v1/core/sessions/current   # 401 정상
grep -c '" 5[0-9][0-9]' ~/Library/Logs/factory-studio/kr.hyudo.fs-api.log
```

## 3. 업데이트 배포 (main 새 커밋 반영)

```bash
cd ~/projects/factory-studio-prod
git checkout --detach main   # 개발 폴더와 같은 저장소라 로컬 main을 그대로 쓴다
uv sync --project backend --frozen --no-dev
uv run --frozen --project backend --env-file .env alembic -c backend/alembic.ini upgrade head
# 시드 버전이 바뀐 경우만: (cd backend && uv run --frozen --env-file ../.env python -m seed.cli template --date $(TZ=Asia/Seoul date +%F))
(cd frontend && PATH=/opt/homebrew/opt/node@24/bin:$PATH npm ci && npm run build)
(cd card && PATH=/opt/homebrew/opt/node@24/bin:$PATH npm ci && npm run build)   # 명함 페이지
launchctl kickstart -k gui/$(id -u)/kr.hyudo.fs-api
```

배포 전 백업(맥북 안):

```bash
mkdir -p ~/fs-backups && docker exec factory-studio-prod-db-1 pg_dump -U factory_studio -Fc factory_studio < /dev/null > ~/fs-backups/$(date +%Y%m%d-%H%M).dump
```

## 4. 운영자 계정

비밀번호는 입력해도 보이지 않고 해시만 저장된다. **사용자가 직접 실행한다.**

```bash
cd ~/projects/factory-studio-prod && uv run --frozen --project backend --env-file .env python tools/create_member.py <아이디> --name "관리자" --admin
```

## 5. 멈추기 · 되돌리기

```bash
for s in cloudflared fs-api fs-cleanup; do launchctl bootout gui/$(id -u)/kr.hyudo.$s; done; brew services stop nginx
docker stop factory-studio-prod-db-1
```

터널·DNS 삭제는 `cloudflared tunnel route`로 만든 CNAME 3개(eip·www·apex)를 Cloudflare 대시보드에서 지우고 `cloudflared tunnel delete factory-studio-mac`.

## 6. 2026-11-22 확인 결과

- **HYUDO-03 반영(같은 날):** www → 명함 페이지 200, apex·`eip/about` 301 → www, 이미지·파비콘 200. 배포 전 DB 백업 `~/fs-backups/20261122-1556-before-hyudo03.dump`. Nginx 이전 설정 `nginx.conf.before-hyudo03`.


- 로컬: 화면 200, API 401, www 302 → `/about`, 모르는 이름 444, 정리 작업 1회 종료 코드 0(`cleaned_guest_workspaces=0`).
- 공개: `https://eip.hyudo.kr` 200, API 401, `www`·apex 302 → `https://eip.hyudo.kr/about`, `http://` 301 → https. 터널 연결 4개(icn05·06·07).
- 내장 브라우저: www → `/about` 표시, 게스트 생성 → `/home` 솔루션 10개 표시, 세션·FEMS 에너지원·ERP·MES 대시보드 200. API 로그 5xx 0, 방문자 IP 전달 확인.
- 미확인: 재부팅 후 자동 복구(실제 재부팅 안 함), 관리자 로그인(계정 미생성), 전 화면 회귀, 휴대폰 실기기.
- 예전 운영 데이터는 없다(Vultr 삭제). DB는 시드로 새로 시작했다.

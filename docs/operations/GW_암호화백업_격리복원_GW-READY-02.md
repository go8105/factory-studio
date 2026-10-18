# GW 암호화 백업·격리 복원 · GW-READY-02

개발 브랜치의 서버 운영 도구다. 원본 DB를 덮어쓰거나 직원 접속을 자동으로 열지 않는다. 실제 회사·외부 저장소·운영 인수는 미완료이며 운영 준비는 false다. 지정한 PostgreSQL DB 전체를 백업하므로 GW 회사 한 곳의 문서 내보내기 기능과 구분한다. 다른 솔루션의 업무 정책까지 인수한 결과가 아니다.

## 현재 결과의 의미

- BACKUP PASS: 같은 DB 스냅샷의 덤프·테이블별 행 수/지문·버전/키 식별자 명세를 암호화하고, 로컬 파일을 동기화한 후 복호화 인증·서명·덤프 지문을 다시 확인했다는 뜻이다. 외부 보관 성공·장애 전환·실제 회사 RPO 보장이 아니다.
- RESTORE PARTIAL: 새 격리 DB로 복원해 보안 재적용 **전** 행 수/지문/FK/head를 대조하고 기존 세션·진행 중 인증 요청을 회수했다. 별도 기록에서 확인한 제한만 재적용한다. 도구는 `checkpointRestrictionsApplied=true`, `checkpointCompletenessConfirmed=false`, `revocationsReapplied=false`, `twoAccountChecks=false`로 기록하며, 전체 회수의 누락 없음이나 실사용 인수를 자동 인정하지 않는다.
- 실패/불명확 결과는 성공으로 바꾸지 않는다. 실패한 새 DB는 ALLOW_CONNECTIONS=false로 추가 동결하고 비공개 보고를 진단용으로 보존한다. 동결 명령 자체의 확인 여부도 보고에 남긴다. 기존 DB/파일을 자동 삭제·덮어쓰지 않는다. 정상 부분 복원도 운영 앱·worker를 연결하지 않는다.

## 서버 준비

Python3.14/uv와 서버와 같은 주 버전의 pg_dump/pg_restore가 필요하다. 이번 실제 검사는 PostgreSQL18.6이다. 로컬 기본 도구16.15는18 서버용으로 사용하지 않았다. `FS_GW_PG_BIN`에 PostgreSQL18 도구 폴더를 지정하거나 서버의 PG 컨테이너를 명시한다. 컨테이너 경로는 `docker exec` 접근 권한이 있는 별도 운영자용이며 비특권 앱 프로세스에 Docker 권한을 주지 않는다.

백업은 pg_control_system 조회와 전 DB 읽기/스냅샷 내보내기 권한을 요구한다. psql로 도구 연결이 같은 실제 DB를 가리키는지도 확인한다. 복원은 DB 생성과 접속 제한 설정이 가능한 별도 관리자 연결이 필요하다. 일반 웹 API에서 이 권한을 제공하지 않는다. PostgreSQL 로그인 역할/클러스터 설정/WAL 연속 복구·외부 객체/첨부 저장소·OS 비밀은 이 DB 파일만으로 복원하지 않는다. 새 대상은 `fs_gw_restore_<난수>_test`로 자동 생성한다. 다른 DB 이름 지정/clean/덮어쓰기 옵션이 없다.

| 비공개 환경 설정 | 의미 |
|---|---|
| DATABASE_URL | 원본 PostgreSQL 연결. 명령행에 넣지 않음 |
| FS_GW_RESTORE_ADMIN_URL | 격리 복원 서버 관리자 연결. 운영 앱 연결로 쓰지 않음 |
| FS_SECURITY_MODE / FS_SECURITY_KEY_ID / FS_SECURITY_KEYS | 기존 회사 보안 설정과 인증 암호화 키. PUBLIC_DEMO 실행 거부 |
| SESSION_SECRET | 기존 서버 인증 설정. 키 값은 문서·로그에 넣지 않음 |
| FS_GW_BACKUP_KEY_FILE / FS_GW_BACKUP_KEY_ID | 별도32바이트 AES 키 파일·식별자 |
| FS_GW_RUNNER_KEY_FILE / FS_GW_RUNNER_KEY_ID | 별도32바이트 Ed25519 비밀 키 파일·식별자 |
| FS_GW_EVIDENCE_PUBLIC_KEYS | 실행자 공개 키 원시32바이트의 base64 JSON. 비밀 키와 일치해야 함 |
| FS_CODE_REVISION | 실제 배포 제품 Git revision. 배포 산출물과 대조하며 임의 과거값으로 맞추지 않음 |
| FS_GW_PG_BIN | 기본 PG 도구 폴더. 미설정이면 PATH 사용/주 버전 검사 |
| FS_GW_PG_CONTAINER / FS_GW_RESTORE_PG_CONTAINER | 명시할 경우 해당 컨테이너의 PG 도구 사용. 내부 연결 포트5432. 원본/복원 서버를 각각 확인 |

키는 기존 것을 무작정 재생성하지 않는다. 새 키가 필요한 최초 준비 시 안전한 난수/Ed25519 라이브러리로 파일에 직접 생성하고 별도 보관한다. 비밀 값을 표준 출력·명령행·Git에 넣지 않는다. 키 파일은 운영자 소유0600, 작업/보관 폴더는0700, 기존 출력 파일은 덮어쓰지 않는다. 백업 키와 서명 키는 백업 폴더 안에 둘 수 없다. 백업 키와 기존 인증 키를 모두 잃으면 복구를 보장할 수 없다.

현재 묶음 한도는 **평문 tar 기준1GiB**다. DB 덤프는 custom 압축 형식이며 전체 묶음은 스트리밍 AES-256-GCM으로 암호화한다. 비공개 임시 폴더 안에서만 평문을 만들고 종료 시 제거한다. 인증 태그를 확인하기 전에는 복원하거나 명세를 해석하지 않는다. manifest·권한 대조 기록도 암호화 묶음 안에 있다. 별도 JSON 증거에는 원문/인증 비밀/DB URL을 넣지 않는다.

## 최초 백업 키 준비 예시

**기존 운영 키를 바꾸는 명령이 아니다.** 최초 준비 때만, 실제 백업을 실행할 동일 운영자 계정으로0700 키 폴더를 먼저 준비하고 경로를 바꿔 실행한다. 출력 파일이 하나라도 있으면 중단하며 비밀을 출력하지 않는다. 이미 백업이 있다면 기존 키/식별자를 보존하고 이 예시로 대체하지 않는다.

```sh
uv run --project backend python - <<'PYKEY'
import base64, json, os
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fs.core.backup import create_private, private_directory
task_key_dir = private_directory(Path('/private/operator-keys'))
paths = [task_key_dir / name for name in ('backup-aes256.key', 'runner-ed25519.key', 'runner-public.json')]
if any(path.exists() for path in paths):
    raise SystemExit('기존 파일이 있어 생성하지 않습니다.')
signer = Ed25519PrivateKey.generate()
public = {'runner-1': base64.b64encode(signer.public_key().public_bytes_raw()).decode()}
for path, data in zip(paths, (os.urandom(32), signer.private_bytes_raw(), json.dumps(public).encode())):
    with create_private(path) as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
print('비공개 키 파일과 검증 공개 키 파일을 저장했습니다.')
PYKEY
```

이 예시의 서명 식별자는 runner-1이다. 백업 키 식별자는 운영자가 정한 안전한 이름을 사용한다. 공개 키 JSON만 앱의 검증 설정에 반영하고 두 비밀 키 파일은 백업 도구의 별도 파일 설정으로만 연결한다. 실제 서버 인증 키(FS_SECURITY_KEYS)를 이 예시의 백업 키로 덮어쓰지 않는다. 별도 보관·복원 시험 전에는 최초 키 준비도 운영 인수 완료로 표시하지 않는다.

## 백업과 현재성 확인

저장소 루트에서 서버 비공개 환경을 주입한 뒤 실행한다. 아래 경로는 운영 담당자가 준비한0700 폴더의 예시다.

```sh
uv run --project backend python tools/gw_backup.py backup \
  --company-id COMPANY_ID \
  --output /private/backups/RUN/database.fsbackup \
  --evidence /private/backups/RUN/evidence.json

uv run --project backend python tools/gw_backup.py check \
  --backup /private/backups/RUN/database.fsbackup
```

check는 원본 DB와 서명된 파일을 대조해 현재 정책/세대·제품·DB 버전·스냅샷 나이를 검사한다. 종료0은 해당 로컬 파일이 현재 조건에 맞음,3은 오래됨/기준 변경,1은 설정·손상·실행 오류다. 원본 DB가 없으면 현재성을 추측하지 않는다. 파일을 직접 지정하는 검사이며 최신 파일 자동 선택·새 실패 탐지·외부 저장소 검증을 대신하지 않는다. 스냅샷 시작 시각부터 RPO를 계산하고 백업 끝 시각부터 짧게 계산하지 않는다.

성공 증거 JSON은 제품 **회사 운영 안내 → 운영 준비 → 운영 실행 기록**에서 등록한다. 서버에 현재 정책·제품/DB와 맞지 않으면 거부한다. 원문 백업 파일이나 키는 제품 파일 선택에 넣지 않는다.

## 별도 권한 대조 기록

백업 이후 정지/회수 내역이 옛 DB에서 되살아나는 것을 막기 위한 별도 암호화 기록이다. 원본과 같은 PG 인스턴스/DB인지 지문으로 확인하고, 백업 실행 ID·명세 지문과 결합한다.

```sh
uv run --project backend python tools/gw_backup.py checkpoint \
  --backup /private/backups/RUN/database.fsbackup \
  --output /private/revocations/RUN/checkpoint.fsbackup \
  --head /private/revocations/RUN/head.json
```

출력의 checkpointDigest(비밀이 아닌64자리 지문)를 최신 기록으로 **독립된 관리 기록**에도 보관한다. head와 checkpoint를 백업과 다른0700 폴더에 보관해야 한다. 다른 폴더만으로 다른 디스크·외부 보관이 확보되지는 않는다. 전체 폴더와 최신 지문이 함께 과거로 되돌아간 경우를 이 도구만으로 탐지할 수 없다. 독립 보관/변조 방지 저장소·담당자 대조가 필요하다.

현재 checkpoint는 운영자가 명시 실행하는 시점의 일관된 상태다. **모든 보안 변경에 대한 자동 외부 기록 연결과 누락 없는 연속성 검증은 아직 미구현**이다. 파일 누락/잘못된 최신 지문/백업 연결 불일치/백업보다 오래됨/RPO보다 오래됨은 거부하지만, 생성 후 아직 기록하지 않은 회수를 추측하지 않는다. 이 제한 때문에 복원 증거는 계속 PARTIAL이다. 장애 시 원본이 남아 있다면 접속·권한 변경을 중지하고 최신 기록을 별도 확인해야 하며, 자동으로 운영 재개하지 않는다.

## 새 격리 DB 복원

운영 직원 접속·외부 발송·worker를 연결하지 않은 별도 서버에서 실행한다. 대상 DB 이름은 입력하지 않는다. 새 이름은 보고 JSON에 남는다.

```sh
uv run --project backend python tools/gw_backup.py restore \
  --backup /private/backups/RUN/database.fsbackup \
  --checkpoint /private/revocations/RUN/checkpoint.fsbackup \
  --head /private/revocations/RUN/head.json \
  --expected-checkpoint-digest "${GW_RECOVERY_CHECKPOINT_SHA256:?독립 확인한 최신 지문 필요}" \
  --report /private/recovery/RUN/report.json \
  --evidence /private/recovery/RUN/evidence.json
```

복원은 같은 제품 revision·PG 주 버전·인증 암호화 키 식별자를 요구한다. DB의 테이블별 행 수/지문과 FK/head를 먼저 대조하고, 이후 보안 제한을 반영한다. 그래서 보안 재적용 후 전체 DB 지문이 원본과 같아야 한다고 해석하지 않는다. schema219표 외에 migration 버전 표도 지문 목록에 포함한다.

- 모든 기존 인증 세션을 회수하고 미완료 인증 요청을 만료시킨다. 사용된 복구 코드와 더 높은 OTP 사용 구간·실패 제한은 되돌리지 않는다.
- 변경/삭제된 계정 인증 정보는 새 비밀번호나 권한으로 임의 승격하지 않고 확인 전 정지한다. 옛 비밀번호·로그인 ID를 되살리지 않는다.
- 회사 멤버십·GW 직원 연결/역할/열람자·HR 출퇴근 계정의 권한 하향·정지를 제한 방향으로만 반영한다. 위임은 자동 재개하지 않는다.
- 조직/결재선/전결/재배정/채팅·일정 참여/게시 공개 범위/운영 기준·보류의 차이가 있으면 해당 GW 범위의 연결을 격리하고 회사 보존 중지를 설정한다. 누락된 새 원문이나 권한을 추측해 복사하지 않는다. 별도 대조·복구 계획 없이 연결을 다시 활성화하지 않는다.

접속 제한은 PUBLIC CONNECT 회수와 DB 접속수0이다. PostgreSQL superuser는 접속수 제한을 우회할 수 있으므로 관리자 경계·네트워크/pg_hba·앱/worker 미연결을 별도로 확인해야 한다. 사용자용 접속을 여는 명령은 없다. DB와 실행자 사이 최대30초 시계 차이를 검사하고 미래 기록도 그 범위까지만 허용한다. 결과 JSON의 보수적 경과 구간에는30초 여유를 포함하며 실행 시간과 남은 인수를 함께 기록한다. 실제 손실 데이터 범위·RPO/RTO 보장은 아니다. 관리자/직원 업무와 회수 계정 거부를 실제 환경에서 확인하기 전 운영으로 전환하지 않는다.

## 30분 스케줄 템플릿

`deploy/gw-backup/factory-studio-gw-backup.service`와 `.timer`, `tools/run_gw_backup.sh`를 제공한다. 설치/활성화하지 않았다. 기본은 UTC 매시00/30분이며 운영 정책을 바꿨다고 서버 타이머가 자동 변경되지 않는다. 루트 폴더·회사ID·uv 경로·별도 운영자·환경 파일·백업 도구 권한을 실제 서버에 맞춰 검토한다.

운영 담당자의 최초 설치 예시(이번 작업에서 실행하지 않음):

```sh
systemd-analyze calendar '*-*-* *:00,30:00 UTC'
systemd-analyze verify deploy/gw-backup/factory-studio-gw-backup.service deploy/gw-backup/factory-studio-gw-backup.timer
sudo install -m 644 deploy/gw-backup/factory-studio-gw-backup.service /etc/systemd/system/
sudo install -m 644 deploy/gw-backup/factory-studio-gw-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start factory-studio-gw-backup.service
# 첫 실행 결과·별도 보관·복원 시험을 확인한 뒤 활성화
sudo systemctl enable --now factory-studio-gw-backup.timer
systemctl list-timers factory-studio-gw-backup.timer
```

서비스 환경 파일은 서버에서0600으로 준비한다. FS_GW_BACKUP_ROOT(0700), FS_GW_BACKUP_COMPANY_ID, FS_UV_BIN과 위 비공개 설정이 필요하다. 실행별 새 폴더에 SUCCESS/FAILED를 남긴다. 실패는 서비스 실패로 끝나며 자동 삭제/보관 기간 청소·알림 서비스 연결·증거 자동 등록은 미구현이다. 운영 담당자가 마지막 성공 시각·실패·현재성 검사와 외부 사본을 확인해야 한다. 로컬 bash 문법만 검사했으며 실제 Linux systemd 기동은 미검증이다.

## 근거와 현재 검증

[PostgreSQL pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html), [cryptography GCM 인증 완료 조건](https://github.com/pyca/cryptography/blob/main/docs/hazmat/primitives/symmetric-encryption.rst), [systemd 시간 표현](https://www.freedesktop.org/software/systemd/man/latest/systemd.time.html)을 참고했다. 서명은 실행 주체/변조 여부를 확인하며 실행자나 키 자체의 침해를 해결하지 않는다.

실제 PG18 합성 DB에서 암호화 CLI·복호화/서명 자체검사·새 DB 복원·지문/FK·세션 무효화·연결 정지 재적용 후 관리자200/직원403·옛 세션401을 확인했다. 변조/다른 키/기존 파일 보존·최신 지문 불일치·실패 DB 보존·OTP/복구 코드 소비·옛 비밀번호·HR 권한 하향·회사 보존 중지도 검사했다. 실제 사용자 데이터/공유 DB/실서버 스케줄/운영 배포는 변경하지 않았다.

다음은 독립 회수 기록 자동 수집·연속성/누락 검증·외부 저장소·실환경 복구 인수와 운영 준비 판정, 선택SSO·전체 회귀다. [전체 구현 기록](../agent/GW_실사용구현_GW-READY-02.md), [제품 도움말](../../content/help/gw/operations.md).

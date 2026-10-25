# GW 실회사 인수 절차 · 10인 기본안

2026-10-19 / GW-READY-02 21차. 제품 구현·합성 검증과 실제 회사 도입 인수를 구분한다. 이 문서는 인수 계획이며 통과 증거나 운영 승인이 아니다.

## 현재 위치

회사 인증/권한, MFA·제한 복구·긴급 복구, 운영 기준/서명 증거 등록, 암호화 백업·접속 제한 격리 복원, 변경 기록·보존 폴더 교체·전달 확인, 원본 증거 재검증을 구현했다. 관련 합성 HTTP/DB/화면 검사 결과는 [진행 기록](../progress.md)에 차수별로 남겼다. 이 결과를 모든 기능의 전체 CI나 실제 외부 장애 검증으로 합산하지 않는다.

운영 준비 화면은12조건을 판정한다. 외부 저장소/전체 수집·회수/실제 회사/최종 전환4조건은 인수 증거 연결이 없어 미확인이다. 이번에는 필요한 근거를 제품에 안내하며, 이 안내를 입력했다고 통과로 인정하는 기능은 없다. ACCEPTANCE PASS와 네 조건의 최종 증거 수집·검증 어댑터는 후속 구현이다. 따라서 현재는 실제 사업 운영을 바로 시작할 수 있는 인수 완료 상태가 아니다.

## 최소 인원 기본안

- 회사1개·부서1개·직원10명. 회사 관리자1명과 직원9명을 기본으로 하되 실제 책임자/결재 역할은 기존 직원에게 배정한다.
- 플랫폼 총 관리자(아이디 admin)와 회사 관리자는 다른 권한 범위다. 총 관리자 계정을 직원 공용 계정으로 쓰지 않는다. 비밀번호·실제 개인정보를 이 문서에 기록하지 않는다.
- 운영/복구 담당 역할은 회사 직원을 겸할 수 있으나 서버 권한과 회사 권한은 구분한다. 긴급 복구의 요청자·승인자 분리와 현재 역할 재확인을 우회하지 않는다.
- 도입 전10명의 실제 본인 연결·전원MFA와 회사 관리자/직원의 대표 업무를 확인한다. 실제 계정은 사용자가 도입을 시작할 때 운영 절차로 준비하며 이번 개발에서 만들지 않았다.

## 1. 코드·환경 인수 준비

최신 로컬 main과 작업 브랜치를 대조하고 충돌/마이그레이션 경로를 검토한다. 전체 회귀·기존 CI·10인 동시 사용/장기 부하를 검증한다. 합성 TEAM_TEST 결과를 실제 COMPANY/TLS/시간 동기/키 분리/모바일 기기 인수로 바꾸지 않는다. 도입 제품/DB 버전과 현재 회사·세대/정책 지문을 고정해 증거가 같은 대상을 가리키도록 한다.

## 2. 미확인 근거 수집·검증 연결

제품 **운영 준비 → 운영 전환 조건 → 필요한 인수 근거**에 네 조건의 필요한 자료와 합성/실환경 구분을 표시한다. 실제 자료는 허용 필드·크기·서명자·회사/세대·정책/제품/DB 버전·시각·실행 번호·원본/사본 지문을 검증하는 계약으로 연결해야 한다. 원문·비밀·임의URL 업로드나 수동 완료 체크로 대체하지 않는다. 이 검증 연결은 아직 구현하지 않은 후속 범위다.

## 2-1. 백업·복원 자료 대조 수집기 · 구현됨

`tools/gw_acceptance_collect.py`는 기존 `gw_backup.py`가 만든 백업·복원 서명 증거 파일을 읽어 대조한다. DB에 접속하거나 회사 준비 상태를 변경하지 않는다. 현재 기준은 증거 파일에서 복사해 신뢰하지 말고 운영 담당자가 현재 회사·세대·정책/제품/DB 버전에서 별도로 준비한다.

1. 운영자 전용0700 폴더에0600 일반 파일로 현재 기준 JSON을 준비한다. 필드는 `workspaceId`/`generationId`(양의 정수), `policy`(현재 OperatingPolicy 전체, `responsiblePersonId`·`reason` 포함), `codeRevision`, `dbRevision`이다. 비밀번호·DB URL·개인정보는 필요하지 않다.
2. 백업/복원 도구가 출력한 `{envelope, signature}` 원본 증거를 같은 권한으로 준비한다. 현재 신뢰 공개 키를 기존 `FS_GW_EVIDENCE_PUBLIC_KEYS` 환경 설정에서 읽는다. 서명 개인 키·DB 접속 정보는 이 도구에 제공하지 않는다.
3. 저장소 루트에서 다음을 실행한다. 예시 경로는 새 비공개 작업 폴더 안의 합성 파일명이며 기존 자료를 덮어쓰지 않는다.

```sh
uv run --project backend python tools/gw_acceptance_collect.py \
  --context work/acceptance/current.json \
  --backup work/acceptance/backup-proof.json \
  --restore work/acceptance/restore-proof.json \
  --output work/acceptance/collection.json
```

각 파일의 서명·범위·현 정책/버전·기한·PASS 검사와 백업의 RPO 현재성을 재검증한다. 두 증거의 manifest 지문이 같고 서로 다른 실행 번호이며 백업 종료 뒤 복원이 시작했는지도 대조한다. 최신 DB 등록 기록을 조회하지 않으므로 담당자가 고른 파일 쌍만 검사하며, 더 최신의 실패 기록이 없다는 보장은 하지 않는다.

결과에는 검사 상태와 검증한 원본 증거의 지문, 회사/세대/정책/제품/DB 기준·수집 시각을 남기고 파일 경로·서명·키·증거 원문은 넣지 않는다. 쌍이 맞으면 `PARTIAL`/종료0, 누락·변조·불일치·기한 초과·일부 확인이면 `BLOCKED`/종료2다. 입력/파일 권한 오류는 종료1이며 기존 출력은 덮어쓰지 않는다. **종료0은 운영 인수 통과가 아니다.** 결과는 서명된 ACCEPTANCE 증거가 아니므로 제품 실행 기록에 업로드할 수 없다. 외부 저장소·전체 수집/회수·실회사·최종 전환 네 조건과 실제 원본 사본의 내구성 검사는 여전히 별도다.

## 2-2. 제품의 최신 등록 증거 대조 · 구현됨

`GET /api/v1/gw/operations?companyId=` 응답의 `backupRestoreCollection`은 회사 보안 관리자/감사 역할에게만 제공된다. 기존 회사 트랜잭션 안에서 현재 정책과 종류별 최신 등록행을 읽고, 정책 revision/현재 신뢰키·제품/DB 버전·기한·원본 서명과 등록행 전체 대조를 거친 후 위 수집기에 연결한다. 정렬은 `recorded_at DESC, id DESC`이며 과거 성공을 찾는 재시도를 하지 않는다. 별도 추가 조회나 쓰기·완료 입력·DB스키마는 없다.

화면 **실행 증거 확인 → 백업·복원 연결 점검**에서 일치/미확인을 안내한다. 최신 실패/PARTIAL/원본 없는 과거행/행 변조는 차단하며, 다른 백업 지문 또는 복원 시작 시각 불일치도 차단한다. 직원 응답에는 수집 결과를 노출하지 않는다. 정책/검증 설정 미준비도 BLOCKED다. 올바른 쌍이어도 PARTIAL·ready=false이고 기존12조건의 미확인4는 유지된다. 서명된 증거의 주장과 같은 백업을 참조하는지만 대조하며 백업 파일을 직접 복호화/복원하지 않는다. 응답 시점 이후 새 등록/키·정책 변경이 생기면 다시 조회해야 하며 결과를 영구 운영 승인으로 보관하지 않는다.

## 2-3. 실제 복원 결과의 부분 검사 전달 · 구현됨

복원 도구는 기존 PARTIAL/failedCheckCount1을 유지하면서 `metrics.restoreDiagnostics` v1에 DB접속 차단/DB버전 일치/권한 제한 적용/완전성 미확인과 변경 대상·미확인·격리 범위 건수를 서명한다. 경로/DB명/계정/원문/키는 진단에 넣지 않는다. 타입/허용필드/0~10000000 건수·미확인<=대상 수를 검증하며 복원 종류에만 허용한다. 이 값이 미확인/미충족인 PASS는 거부한다. 기존 진단 없는 서명 증거의 검증 계약은 유지한다. JSON 기존 metrics에 보관하므로 DB스키마 변경은 없다.

수집기와 최신등록 API는 원본과 저장행 대조를 통과한 PASS 또는 PARTIAL 복원만 `restoreMeasurements`로 전달한다. PARTIAL의 내용 표시가 백업·복원 쌍 통과를 뜻하지 않으며 `backupRestorePairVerified=false`와 ready=false를 유지한다. BACKUP/RESTORE가 다른 지문일 때도 최근 복원 자체의 검사값은 표시할 수 있으므로 쌍 연결 결과와 구분한다. 실패/원본없음/변조/옛 정책·버전은 이 값을 노출하지 않고 이전 성공으로 대체하지 않는다. `최근 복원 검사 내용`은 기본 접힘이며 미등록/검증 설정 미준비에서는 확인된 기록 없음 안내다. 실제 10인 업무/외부 저장소·전체 회수 확인은 후속이다.

## 기존 GW 연결과 UI 보완 항목

현재 운영 준비는 기존 `GwLayout`의 **회사 운영 안내 → 운영 준비**로 연결된 관리자 화면이다. 기존 결재·게시·일정·채팅과 별도 솔루션을 생성하지 않았다. `?companyId=`는 선택 회사 범위를 유지한다. 일반 직원 업무 화면과 관리자 운영 화면을 구분해야 한다.

사용자 피드백(2026-10-20): 별도 GW처럼 보이며 UI 구성이 미완성으로 느껴진다. 36차에서 기존 GwLayout의 회사명/연결 직원·공간 선택과 현재 운영 메뉴 표시를 보완했다. 운영 준비 상단에 연결/예정 인원·관리 역할·우선 조치·회사 범위를 유지한 업무 복귀를 두고, 전환 조건/증거/정책/보관 검토/계정 복구를 구획화했다. 확인된 조건과 긴 근거·긴급 복구 입력은 펼침으로 확인한다. 모바일은 세로 읽기 순서·44px 주요 이동/펼침·가로 넘침을 점검했다.

실제 합성 미리보기 계정의 기존 로그인/MFA로 현재 제품과 실제 API를 연결해 회사·미완료 표시, 정책 패널의 입력 유지/포커스 복원/버리기, 회사 업무 복귀를 확인했다. 별도 합성 API 응답 화면에서는 복원 PARTIAL 세부 표시와 조건 이동을 확인했다. 이 둘을 실제 회사/10인 인수로 표현하지 않는다. 기존 예정10/연결1과 서버 검증 설정 필요·ready=false/미확인4는 유지된다. 사용자의 전체 UI 만족도와 실기기/10인 사용 검증은 남아 있다.

## 3. 외부 저장소 장애·복구

실제 다른 장애 영역의 저장소와 최소 권한·변경 방지·별도 키 보관을 준비한다. 원본에 접근할 수 없는 상태에서 사본 전체 읽기·지문/서명 확인·새 격리 DB 복원을 수행하고 RPO/RTO를 측정한다. 전달 확인의 HMAC/현재성만으로 저장 장치 독립성과 내구성을 통과시키지 않는다. 실제 저장 장소/자격 증명은 아직 설정하지 않았다.

## 4. 전체 변경 수집·권한 회수

[운영 경로v1](GW_보안변경_수집경로검증_GW-READY-02.md)을 현재 코드와 대조한다. 예상 변경/암호화 의도/같은 거래 감사 지문을 비교하고, 미확인·분기·누락·저장 실패와 직접SQL/초기설정·재생제외 경계를 처리한다. 최신 권한 대조 뒤 옛 토큰/미완료 요청/회수 권한 거부와 원본 유지까지 확인한다. 앞선 합성 검사는 이 근거의 일부이며 실제 운영의 무누락을 자동 인정하지 않는다.

## 5. 실제10인 업무 인수

전원 연결·MFA·담당자/조직과 관리자/직원의 결재·게시·일정·알림·채팅 등 대표 흐름을 실제 역할로 확인한다. 실제 기기에서 로그인/추가 인증/복구/로그아웃·회수 계정 거부와 오류 안내를 검증한다. 동시 사용/부하·복구 시간·미해결 문제를 기록한다. SSO를 선택해 사용할 경우 실제 IdP 연결과 회수/장애 인수도 별도로 수행한다. 미사용 SSO를 동작 확인한 것으로 표시하지 않는다.

## 6. 최종 전환

책임자가 현재 회사/세대·정책·코드/DB 버전에 묶인 앞선 결과와 미해결 항목을 검토한다. 모니터링·장애 연락·백업/복구 담당·되돌림 기준을 준비하고 기존 배포 절차/회귀 후 실제 접속 전환을 확인한다. 이 문서나 합성 복원본을 근거로 기존 접속 제한 DB를 임의 개방하지 않는다. 원본 변경·실서버 배포·원격 push는 이번21차 범위에서 수행하지 않았다.

## 완료 보고에 남길 항목

항목별 회사/세대·정책/제품/DB 버전, 실행 번호·시각·검증자 역할, 사본/명세 지문, 허용 손실/복구 측정치, 검증 범위·미해결 문제·운영 인계 위치를 남긴다. 비밀번호·토큰·복구 코드·실제 업무 원문은 기록하지 않는다. 근거 없는 항목은 미확인으로 유지한다.


## 2-4. 가져온 암호화 사본 전체 읽기 · 26차 구현

기존 수집 명령에 `--storage-copy work/acceptance/copied-backup.enc`를 추가하면 담당자가 외부 보관에서 가져온 사본을 직접 끝까지 읽어 현재 서명 BACKUP PASS의 artifactDigest와 비교한다. 소유자 비공개 일반 파일(최대1GiB, 빈 파일·최종 심볼릭 링크 금지)만 읽고 읽기 전후 크기/변경 시각도 대조한다. 경로·내용·키는 보고에 넣지 않는다. 자동 다운로드/외부 자격 증명/원본 접근/DB 연결은 없다.

`storageCopy.state=MATCH`는 바이트 지문 일치만 뜻한다. 저장소 장애영역 독립성·내구성·복호화 확인은 아니며, 네 조건과 ready=false를 유지한다. MISMATCH는 다른 증거 쌍이 맞아도 BLOCKED/종료2다. 파일/서명·현재성 오류는 종료1이며 기존 결과를 덮어쓰지 않는다. 이 보고는 서명된 ACCEPTANCE 증거가 아니며 제품에 등록하지 않는다. 최신 등록 실패 여부는 기존 제품 조회에서 별도로 확인해야 한다.


## 2-5. 사본 복호화·내부 명세·dump 검사 · 27차 구현

기존 백업 도구의 `verify-copy`는 원본DB 없이 가져온 암호화 사본을 검증한다. §2-1의 현재 기준/신뢰 공개키와 `FS_GW_BACKUP_KEY_FILE`(0600·32바이트 복호화키), `FS_GW_BACKUP_KEY_ID`를 준비한다. 서명 개인키·인증키·DB URL은 제공할 필요가 없다. 키를 명령행이나 보고서에 적지 않는다.

```sh
uv run --project backend python tools/gw_backup.py verify-copy \
  --backup work/acceptance/copied-backup.enc \
  --backup-evidence work/acceptance/backup-proof.json \
  --context work/acceptance/current.json \
  --report work/acceptance/copy-check.json
```

새0700 임시폴더에 사본을 제한 복사한 뒤 현재 서명 증거/지문을 확인하고 같은 사본을 복호화한다. 내부 명세 서명과 dump지문, 증거의 manifestDigest/runId까지 대조한다. 성공·실패 모두 임시 암호문/평문을 제거한다. 새0600 보고서는 지문/버전/검사값만 담으며 경로·원문·키는 제외한다. 성공은 PARTIAL/종료0, 오류는 종료1이다. 기존 보고서를 덮어쓰지 않는다.

`decryptionConfirmed=true`/`dumpDigestVerified=true`는 파일 무결성 범위다. `databaseRestoreConfirmed=false`와 저장소 독립성 미확인은 유지한다. 실제 PostgreSQL 복원/권한회수·실회사 인수와 구분하며 이 unsigned 보고서는 제품 실행 증거에 등록하지 않는다. 최신 실패 여부는 기존 제품 등록조회에서 별도 확인해야 한다. 27차는 합성 dump 바이트 검사였고,28차에서 실제 pg_dump 사본의 오프라인검사→원본 백업 파일 제거→같은 사본의 접속제한PG 복원→manifest 증거 대조를 검증했다. 실제 외부 장애영역/운영 인수 검증은 아니다.


## 28차 실제PG 사본 회귀와 시각 제약

별도 소유 테스트DB에서 실제 사본 검사/격리복원과 기존 journal 두 경로 총3건 최종 통과했다. 사본 파일검사 보고서와 복원 증거는 별개이며 동일 manifestDigest를 대조한다. 기존 PARTIAL·전체회수 미확인·ready=false는 유지한다. 실제 저장소 자격 증명/다운로드나 운영DB 접속은 이번에 추가하지 않았다.

호스트/DB 종료시각 차이에 대해 파일검사는 기존 서명검증과 동일한30초 허용을 사용한다. 백업 시작시각/RPO 현재성 조건은 유지한다. 검증 도중 DB시각 역전으로 기존 CHECK/증거 등록 실패도 관찰했고 최종 재실행은 통과했다. 시간동기 설정을 임의 변경하지 않았으며 장기 안정성이나 운영 시간동기 인수 완료로 해석하지 않는다. 운영 도입 전 실제 서버·DB 시간동기와 시각 역전 대응을 별도로 검증한다.

## 10. 서명된 인수 일부 확인과 최신 원본 대조 (35차)

최종 ACCEPTANCE PASS 전에 사용하는 제한된 계약이다. 기존 백업·복원의 원본 서명, 현재 회사/세대·정책·제품/DB·기한, 동일 백업 명세와 실행 순서를 대조한 결과만 서명한다. **실회사 인수나 최종 전환 승인이 아니다.** 복원 PARTIAL을 그대로 참조하며 기존 백업·복원 연결 점검의 PASS 조건은 바꾸지 않는다. 합성 경로 수집 보고서와 사본 검사 보고서는 입력 원본으로 받지 않는다.

§2-1의 비공개 현재 기준 파일·BACKUP/RESTORE 원본과 공개 키에 더해, 서명 발급 시에만 기존 실행자 키 설정 `FS_GW_RUNNER_KEY_FILE`(0600,32바이트 Ed25519 개인 키)과 `FS_GW_RUNNER_KEY_ID`를 비공개 환경에 제공한다. 개인 키와 현재 공개 키가 일치해야 한다. DB 접속·인증/복호화 키는 이 도구에 필요하지 않다.

```sh
uv run --project backend python tools/gw_acceptance_collect.py \
  --context work/acceptance/context.json \
  --backup work/acceptance/backup-evidence.json \
  --restore work/acceptance/restore-evidence.json \
  --signed-reconciliation \
  --output work/acceptance/acceptance-partial.json
```

출력은 `{envelope, signature}`이며 `metrics.acceptanceDiagnostics`에 원본별 runId/sourceDigest와 네 조건의 UNVERIFIED를 담는다. manifestDigest는 이 대조 명세의 지문이다. 백업 파일의 지문을 인수 명세 지문으로 오해하지 않는다. PARTIAL/종료0만 발급하며 입력 불일치/실패/권한/기존 출력 오류는 종료1이다. 기존 unsigned 명령의 BLOCKED/종료2 동작은 그대로다. `--storage-copy`는 서명 옵션과 함께 사용할 수 없으며 별도 보고서로 검사한다. 기본 unsigned 명령에는 서명 개인 키를 제공하지 않는다.

원본 BACKUP/RESTORE를 먼저 제품에 등록한 뒤 새 일부 확인 파일을 기존 **운영 실행 기록**에서 등록한다. 서버는 현재 운영 기준 잠금 안에서 `recorded_at DESC,id DESC` 최신 원본을 선택해 서명·등록행·참조 실행/지문까지 대조한다. CLI가 선택한 파일만으로 최신성을 주장하지 않는다. 최신 원본이 다르면 등록400이며, 이미 등록한 일부 확인도 다음 운영 준비 조회에서 INVALID가 된다. 최신 실패·새 PARTIAL/성공·원본 없는 기록·변조·옛 정책/버전·RPO 만료를 이전 원본으로 대신할 수 없다. 회사/세대·실행 시각도 일치해야 한다.

출력/등록 성공은 네 미확인 조건을 해제하지 않는다. `ready=false`, 실제 복원 PARTIAL, 최종 ACCEPTANCE PASS 거부를 유지한다. 실행자의 서명은 실행자 식별/무결성 근거이며 침해된 실행자의 주장 자체를 보증하지 않는다. 실환경 실행 어댑터·서명자 신뢰 분리·현재 운영 원본과 최종 인수 계약은 후속이다. 기존 진단 없는 일부 확인/실패 기록도 인수 완료로 해석하지 않는다.

## 11. 외부 저장소 선정 전 공통 사전점검 (37차)

2026-10-20 사용자 결정: 외부 저장소는 아직 미정이며 공급자 연결에 앞서 공통 사전점검을 진행한다. 개발자 관리자 로그인 아이디는 `admin`을 기준으로 한다. 이는 기존 실제 계정을 생성/이름 변경하거나 플랫폼 관리자에게 GW 권한을 자동 부여하라는 뜻이 아니다.

`tools/gw_acceptance_preflight.py`는 서버 운영자가 현재 회사의 인수 기준과 연결 상태를 **읽기 전용으로** 수집하는 도구다. PostgreSQL `REPEATABLE READ`와 `READ ONLY` 거래를 강제하고 현재 회사/세대·GW 활성/초기화/세대 준비·현재 정책 원본 지문·실제 DB head를 읽는다. 제품 버전은 운영자가 신뢰하는 서버 환경의 `FS_CODE_REVISION`을 제공한다. 이 값만으로 실행 코드/배포 버전 검증이 끝나지는 않으므로 보고서에는 `codeRevisionSource=OPERATOR_ENVIRONMENT`, `executionRevisionVerified=false`를 표시한다.

DB 연결은 전용 비공개 `FS_GW_PREFLIGHT_DATABASE_URL`에 제공한다. 일반 DATABASE_URL을 자동으로 사용하지 않으며 명시한 PostgreSQL 연결만 허용한다. 가능한 한 읽기 계정을 사용한다. 비밀번호·OTP·인증/백업/서명 키는 필요하지 않다. 연결 URL이나 비밀을 명령행에 적지 않는다. 출력은 운영자 소유0700 폴더의 서로 다른 새 파일2개로 지정한다.

```sh
uv run --project backend python tools/gw_acceptance_preflight.py \
  --company-id <회사ID> \
  --context-output work/acceptance/current-context.json \
  --report work/acceptance/preflight-report.json
```

기본 관리자 식별자는 `admin`이다. 별도 합성 미리보기 계정을 대조할 때만 `--admin-login <합성계정>`을 명시하며 실제 계정은 변경하지 않는다. 이름은 조회 조건일 뿐 권한 부여 조건이 아니다. 계정 존재/활성·플랫폼 관리자·현재 회사 소속/직원 연결·GW 보안 관리자/감사·MFA 등록과 메뉴 역할 자격을 분리한다. `menuRoleEligible`는 등록 상태에 대한 자격이며 실제 업무 세션과 최근 본인 확인은 `NOT_CHECKED`다. 등록된 역할만 보고 현재 업무 접근이나 변경 가능 여부를 확정하지 않는다.

예정10명/1부서·활성 소속/직원/연결10명·현재 부서 배정·MFA 전원 등록·활성 보안 관리자1명/그 외9명·현재 책임자 연결·지정 관리자 보안 역할/MFA를 점검한다. `NON_EXAMPLE_MARKER`는 DB의 예제 표지만 확인한다. 이 표지가 false여도 합성 회사일 수 있으므로 실제 회사임을 증명하지 않는다. 데이터베이스 등록값은 앱/기기 소유·로그인·업무 성공을 검증하지 않는다.

조건 부족은 `BLOCKED`/종료2, 모든 사전조건 일치는 `PARTIAL`/종료0이다. 오류·현재 기준 부재/변조·파일 권한·기존 출력은 종료1이며 입력 자료를 그대로 성공으로 재활용하지 않는다. 모든 결과에서 ready/liveCompanyAcceptance/releaseAuthorized=false, 대표 업무·기기 검사와 네 최종 조건은 미확인이다. 보고서는 unsigned이고 제품 운영 증거로 등록할 수 없다. 이름·계정ID·비밀번호·MFA 비밀·문서/DB URL/경로를 보고서에 넣지 않는다.

`current-context.json`은 기존 수집기 `--context` 입력의5개 필드(workspaceId/generationId/policy/codeRevision/dbRevision)를 현재 DB에서 생성한다. 정책의 담당자 식별자/사유가 포함되므로 비공개로 보관한다. `preflight-report.json`은 범위/지문/관측 시각/집계와 관리자 자격의 boolean만 담으며 contextDigest로 기준 파일과 연결한다. 출력 성공을 인수 완료로 사용하지 않는다. 두 파일 생성 중 실패하면 이 실행이 새로 생성한 파일만 제거하고 기존/경합 파일은 보존한다.

관측은 한 읽기 거래의 시점 상태다. 이후 계정·역할·정책·세대 변경이나 더 최신 실행 실패가 생기면 다시 점검하고 기존 최신 원본 서명/등록 대조를 수행해야 한다. 이 사전점검은 실행 증거를 선택하거나 과거 성공으로 대체하지 않는다. 외부 저장소 어댑터·실제10인 업무·복구/기기·전체 변경 수집/권한 회수·최종 PASS 계약은 후속이다.


## 12. 사전점검과 합성 10인 업무 실행 연결 (38차)

기존 `tools/gw_route_verify.py`의 고정 카탈로그를 `GW_SYNTHETIC_ROUTE_PROBES_V5`로 확장했다. 새 소유 시험 DB에서 1회사·1부서·관리자1명/직원9명을 구성하고 기존 제품 ASGI API를 호출한다. 운영/미리보기 DB나 실제 계정에는 적용하지 않는다. 새 합성 관리자만 `admin`으로 맞추며 이름으로 권한을 부여하지 않는다.

10명 모두 실제 등록 API의 암호화 TOTP와 확인 API로 등록하고, 등록 전 세션 거부 → 비밀번호의 MFA 도전 → 정상 허용 창 안의 다음 미사용 TOTP → 업무 세션을 확인한다. OTP 재사용 상태·세션 assurance·시계·제품 검증기를 SQL/모의 값으로 통과시키지 않는다. 이 과정의 비밀번호·설정키·OTP·쿠키·복구 코드는 보고서에 포함하지 않는다. 네트워크/TLS·실기기 인증 앱이나 실제 사용자 소유를 검증한 것은 아니다.

현재 회사 사전점검 PARTIAL(10명·1부서·MFA10·보안관리자1·그 외9) 뒤 직원9명의 기안/관리자 승인, 게시/다른 직원 조회, 댓글, 일정 참석, 알림 읽음과 10명 채팅/같은 키 재시도를 수행한다. 직원의 관리 기록403과 타 직원 비공개 초안404도 확인한다. 같은 DB의 최종 사전점검 PARTIAL·현재 기준 지문 일치와 운영 준비 ready=false를 확인한다. 동시 부하/성능·브라우저 UX·업무 모든 분기를 검사하지 않는다.

실행자는 매번 새 runId·현재 checkout 커밋·실 DB head를 시험에 전달한다. 지정한 검사 하나의 성공 JUnit에만 `gwSyntheticBusiness` 속성을 허용하고, 버전/범위/인수 기준 전후 지문·정책 지문·회사/세대·제품/DB·시각·고정 실행 수를 검증한다. 실패/오류/생략/누락/중복·이전 실행/버전·미래 시각·모르는 필드·형식이 다른 수/표지는 관측으로 채택하지 않는다. 허용 필드만 최종 보고서 `syntheticBusinessObservation`에 복사한다. 이 자료와 JUnit은 서명된 제품 증거가 아니며 신뢰하는 시험 실행기/소스 경계 안에서만 의미가 있다. 실행기 침해나 실제 배포 소스를 보증하지 않는다.

전체 고정24검사 정상 종료·현재 관측·실행 전후 소스 지문 일치일 때만 결과 PARTIAL/종료0이다. 새 검사가 성공해도 기존 검사 실패/생략·복원 미확인·관측 부재나 변조는 BLOCKED/종료2다. 소스가 바뀌면 관측도 제외한다. 기존 보고서를 읽어 성공으로 대체하지 않는다. 기존 재현 명령과 비공개 관리 환경 `FS_GW_ROUTE_VERIFY_ADMIN_URL`·`GW_BACKUP_TEST_CONTAINER`·`FS_GW_ROUTE_VERIFY_OWNER`를 사용하고 소유 컨테이너 라벨/loopback 포트를 먼저 대조한다. 새 출력 파일만 허용하고 시험 DB만 정리한다.

`businessObservationState=SYNTHETIC_SCENARIO_PASSED`는 위 한정 시나리오를 뜻한다. ready/liveCompanyAcceptance=false, 실기기/네트워크/실회사 대표 업무 UNVERIFIED를 유지한다. 제품 운영 실행 기록에 등록하지 않는다. 실제 복원 PARTIAL·최종4조건 미확인·ACCEPTANCE PASS 거부도 그대로다. 외부 저장소 선정/실행·실환경 역할별 업무/회수·인수 책임자 검토와 최종 PASS 계약은 남아 있다.


## 13. 현재 DB의 최신 등록 원본에서 서명 일부 확인 수집 (39차)

기존 수집기에 파일 선택 없이 현재 회사 DB에서 원본을 읽는 경로를 추가했다. 기존 파일 방식/진단v1은 유지한다. 서버 운영자가 전용 비공개 `FS_GW_PREFLIGHT_DATABASE_URL`·현재 환경 `FS_CODE_REVISION`·신뢰 공개키와 실행자 개인키/키ID를 준비한다. 권한·키 보관은 §10·11을 따른다. 가능한 한 읽기 DB 계정을 사용하고 URL/비밀번호/키는 명령행에 쓰지 않는다.

```sh
uv run --project backend python tools/gw_acceptance_collect.py \
  --current-company-id <회사ID> \
  --signed-reconciliation \
  --output work/acceptance/current-registered-partial.json
```

이 경로는 `--context`·`--backup`·`--restore`·`--storage-copy`와 함께 사용할 수 없다. 일반 DATABASE_URL을 자동 사용하지 않는다. 기본 `--admin-login admin`은 사전점검 조회 조건이며 계정 생성/이름 변경·역할 부여나 실행자 본인 인증이 아니다. 현재 관리자 조회·인원/MFA 집계가 부족해도 백업/복원의 제한된 대조를 서명할 수 있다. 이를 관리자 자격·10인 사전조건 통과·실회사 인수로 해석하지 않는다.

단일 PostgreSQL REPEATABLE READ/READ ONLY 거래에서 DB 관측 시각·현재 회사/활성 GW 세대·정책 원본/지문·DB head를 확인한다. 같은 스냅샷에서 BACKUP/RESTORE를 `recorded_at DESC,id DESC`로 선택하며 성공·현 정책/버전 필터로 옛 원본을 찾지 않는다. 원본 서명/등록행·실행 번호·현재 정책/제품/DB·시각·백업 현재성과 같은 복원 명세를 대조한다. BACKUP은 현재 PASS가 필요하며 RESTORE PARTIAL은 그대로 PARTIAL로만 참조한다. 최신 실패/원본 없음/변조/옛 정책·버전/미래·만료는 오류/종료1이며 이전 성공을 대신 사용하지 않는다.

출력은 기존 `{envelope,signature}`의 ACCEPTANCE PARTIAL이며 `acceptanceDiagnostics`만 v2/CURRENT_REGISTERED_SOURCES로 확장한다. 원본별 runId/sourceDigest, DB observedAt, 현재5필드 기준의 contextDigest와 네 조건 UNVERIFIED를 서명에 묶는다. 정책 원문/담당자·DB URL·계정·원본 파일·키는 출력하지 않는다. observedAt는 실행 시작과 같아야 하고 현재 범위의 기준 지문을 재검증한다. 진단v1과 v2를 섞거나 최종 PASS로 바꾸면 거부한다. 성공은 PARTIAL/종료0이며 새0600 파일만 생성하고 기존 파일/심볼릭 링크를 덮어쓰지 않는다. 원본/정책/세션/운영 기록을 DB에 쓰지 않는다.

등록은 기존 보안 관리자·최근 본인 확인·회사 범위 절차를 사용한다. 서버가 같은 회사 기준 잠금 안에서 최신 원본을 다시 선택하고 관측 전에 실제로 등록된 원본인지도 확인한다. 운영 준비 조회에서도 재대조한다. 관측 도중 또는 이후 새 실패가 확정됐으면 읽기 스냅샷이 일관돼도 그 결과를 등록할 수 없고, 기존 대조 기록도 무효가 된다. 새 PARTIAL/PASS 원본 역시 실행 번호가 다르면 옛 대조를 무효화하며 새 원본으로 다시 수집해야 한다.

서명은 실행자 식별/무결성 근거이며, DB 관측이 독립 감사 서명이나 배포 소스 검증을 뜻하지 않는다. 침해된 실행자의 주장은 보증하지 않으며 현재 코드 버전도 운영자가 제공한다. 실제 외부 저장소·전체 수집/회수·실회사/기기·전환 자료의 출처/신뢰 분리와 최종 PASS 계약은 남아 있다. ready=false·실제 복원 PARTIAL·최종4조건 미확인·ACCEPTANCE PASS 거부를 유지한다.


## 14. 서명 키별 회사·용도와 인수 발급 키 분리 (40차)

`FS_SECURITY_MODE=COMPANY`에서는 기존 `FS_GW_EVIDENCE_PUBLIC_KEYS`에 더해 서버/도구 환경의 `FS_GW_EVIDENCE_KEY_SCOPES`가 필요하다. 공개키를 믿는 것과 그 키에 해당 회사의 해당 증거를 발급할 권한이 있는 것을 구분한다. 이 설정은 운영자가 관리하며 업로드한 파일의 필드로 권한을 부여하지 않는다. 실제 키나 환경을 이번 개발에서 자동 생성/교체하거나 운영에 적용하지 않았다.

형식(비공개 환경 설정용 합성 예시):
```json
{
  "version": 1,
  "keys": {
    "source-runner": {"workspaceIds": ["3"], "purposes": ["BACKUP", "RESTORE", "CHECKPOINT"]},
    "acceptance-collector": {"workspaceIds": ["3"], "purposes": ["ACCEPTANCE_RECONCILIATION"]}
  }
}
```

`keys`의 이름 집합은 공개키 설정과 정확히 일치해야 한다. 회사ID는 실제 운영자가 선택한 회사의 양수 문자열로 지정한다. 와일드카드·빈 목록·중복/알 수 없는 필드/용도·중복 JSON 키·다른 타입·키 별칭은 거부한다. 두 이름에 동일한 공개키 바이트를 등록해 분리를 우회할 수 없다. 인수 대조 키는 다른 용도를 함께 가질 수 없고 백업·복원·권한 대조 키와 실제 공개키가 달라야 한다. 허용 용도는 BACKUP, RESTORE, CHECKPOINT, ACCEPTANCE_RECONCILIATION, INCIDENT와 §15의 JOURNAL_OBSERVATION이다. 미래의 실환경/최종전환 증거 권한을 임의 이름으로 추가할 수 없다.

서버 등록·운영 준비 재조회·최신 원본 대조와 기존 수집기/백업 도구/오프라인 사본 검사가 같은 정책을 읽는다. 올바른 서명이어도 회사/용도가 맞지 않으면 거부한다. 인수 대조 키로 백업을 만들거나 원본 실행 키로 인수 일부 확인을 발급할 수 없다. 키/용도/회사 권한을 제거한 뒤 재조회하면 기존 원본도 현재 신뢰 정책으로 재검증하며 옛 통과로 대신하지 않는다. 잘못된 설정은 서버 CONFIG_REQUIRED/등록503·도구 오류가 되며 다른 환경/정책으로 자동 전환하지 않는다. PUBLIC_DEMO/TEAM_TEST에서만 설정을 생략한 기존 무범위 키 방식과의 호환을 유지하며 이 무범위 설정 자체를 실회사 운영 설정으로 인정하지 않는다. 기존 서명 원본은 현재의 회사/용도 권한으로 재검증하며, 발급 당시 신뢰 설정의 이력까지 역추적해 증명하지는 않는다. 설정을 명시하면 모드와 관계없이 적용한다.

암호화 백업 내부 명세·권한 대조/최신 지문에도 용도를 적용한다. 새 권한 대조/최신 지문에는 회사/세대/정책 지문만 추가하고 정책 원문/담당자를 추가하지 않는다. 엄격한 설정에서 이 범위가 없는 옛 권한 대조 파일은 새로 수집해야 한다. 복원 실행 키는 새 격리 DB를 만들기 전에 RESTORE 용도를 확인하고, 권한 대조/최신 지문의 범위를 원본 백업과 대조한다. 변경 전 파일을 수정하거나 덮어쓰지 않는다.

별도 공개키는 별도 개인키 바이트라는 기술적 분리다. 개인키 보관자·장애 영역·조직상 독립 검토까지 증명한 것은 아니다. 실제 키 분배/별도 보관·운영자 인계/회수 훈련과 실외부 저장소·전체 수집/회수·실회사/기기·최종전환 어댑터는 남아 있다. admin 로그인 이름이나 GW 관리자 역할을 서명 키 권한으로 대신하지 않는다. ACCEPTANCE_RECONCILIATION은 기존 제한된 PARTIAL/FAIL 범위이며 최종 PASS 발급 권한이 아니다. ready=false·실제 복원 PARTIAL·최종4조건 미확인을 유지한다.


## 15. 현재 회사 GW 변경 기록의 서명 관측 (41차)

기존 `tools/gw_identity_journal.py`에 회사·세대 범위의 `JOURNAL_OBSERVATION` 발급/현재 재대조 경로를 추가했다. 실환경 인수 자료를 구성하기 위한 제한된 관측 계약이며 전체 경로 수집/회수 인수나 ACCEPTANCE 증거가 아니다. 합성 route 수집 보고서와도 별개다. 실제 암호화 기록 원본과 DB 감사·거래 상태를 읽으며 제품/운영 데이터 변경이나 계정·권한 부여를 수행하지 않는다. 파일 잠금은 사용하되 기록 내용/체인을 수정하지 않는다.

관측 전용 공개키에 해당 회사와 `JOURNAL_OBSERVATION` 용도를 명시한다. 예: `{"workspaceIds":["3"],"purposes":["JOURNAL_OBSERVATION"]}`를 §14의 일치하는 공개키 이름에 설정한다. 새 계약은 COMPANY뿐 아니라 모든 모드에서 명시적인 회사/용도 설정을 요구한다. 기존 인수 대조 키와 같은 키/용도를 혼용하지 않는다. 발급 시에만 그 키의 기존 FS_GW_RUNNER_KEY_FILE/ID를 사용한다. 실제 키를 자동 배포하거나 기존 키의 용도를 추가하지 않았다.

전용 비공개 FS_GW_PREFLIGHT_DATABASE_URL, FS_CODE_REVISION, 암호화 기록 경로/키와 별도 최신 지문 설정이 필요하다. 일반 DATABASE_URL을 자동 사용하지 않는다. `--expected-head`는 기존 별도 최신 지문 설정(FS_GW_JOURNAL_EXPECTED_HEAD 또는 전달 확인 설정)과 일치해야 한다. 외부 보관 독립성은 이 지문만으로 증명하지 않는다. 복호화/서명 키·접속 비밀은 명령행/출력/채팅에 적지 않는다.

```sh
uv run --project backend python tools/gw_identity_journal.py \
  --expected-head <별도현재지문> --company-id <회사ID> \
  --signed-observation work/acceptance/company-journal-observation.json
# 재검증에는 발급 개인키가 필요하지 않다. 관측 복호화 키/공개키·현재 기준은 필요:
uv run --project backend python tools/gw_identity_journal.py \
  --expected-head <별도현재지문> --company-id <회사ID> \
  --verify-observation work/acceptance/company-journal-observation.json
```

두 모드는 기존 check-database/classify-transactions/review-report 옵션과 혼용하지 않는다. 발급은 운영자 소유0700 폴더의 새0600 파일만 허용하며 기존 파일을 덮어쓰지 않는다. 결과 PARTIAL이면 종료0, BLOCKED면 종료2, 서명/설정/권한/범위/현재성/원본 오류는 종료1이다. stdout은 결과/ready=false/범위 기록 수만 출력한다. 서명/내부 원문·계정/처리자·업무 내용·DB URL·경로·키를 출력하지 않는다.

단일 REPEATABLE READ/READ ONLY DB 거래에서 현재 회사/활성 세대·정책 원본/지문·DB head와 물리 DB 지문을 읽는다. 암호화 기록은 메타데이터만 대조하며 `gw.company.intent.v2` 중 정확한 회사·세대만 선택한다. HR/core 인증·다른 회사/세대·과거 계열·아예 수집되지 않은 변경을 포함하는 전체 수집 검사가 아니다. 다른 범위의 원문/계정·건수를 보고서에 포함하지 않는다. 전체 체인의 끝 지문은 연결 무결성의 일부로 포함된다.

실제 같은 거래 감사 지문과 PostgreSQL 거래 상태를 대조해 AUDIT_CONFIRMED/ABORT_CONFIRMED/PENDING/SOURCE_MISMATCH/COMMITTED_WITHOUT_AUDIT/UNKNOWN 집계를 만든다. 감사가 있어도 물리 원본/타임라인 근거가 다르면 SOURCE_MISMATCH로 처리한다. 거래 근거가 없는 기록은 별도 수로 표시한다. 대상이 없거나 거래 근거 부족/진행 중/원본 불일치/감사 없는 커밋/미확인이 있으면 BLOCKED다. 선택 기록이 모두 감사 확인 또는 실제 롤백이고 거래 근거도 갖췄을 때만 PARTIAL이다. 사용자 제공 체크/임의 집계로 통과시키지 않는다.

관측 전후 체인을 대조하고 도중 최신 지문이 바뀌면 발급하지 않는다. 서명은 실행 번호·관측 시각·회사/세대·정책/현재 기준 지문·제품/DB·물리 DB·체인/선택 기록 지문·집계를 묶는다. 코드 버전은 운영자가 제공하므로 executionRevisionVerified=false, 전체 수집/권한 회수/실회사/전환/독립 보관/ready는 false다. 단순 서명 검사는 서명/회사·용도/제품/15분 기한만 확인하며, 실제 사용 전에는 verify_current/위 재검증 명령으로 새 DB 스냅샷과 최신 기록/감사/거래 상태까지 다시 대조한다. 이후 지문·정책/세대/버전·물리 DB·감사/거래 결과·키 권한이 달라지면 이전 성공으로 대신할 수 없다. DB와 파일 시스템의 무기한 원자성이나 보관 독립성은 주장하지 않는다.

이 파일은 제품 운영 실행 기록에 업로드하지 않으며 API도 거부한다. 관측 실행 이력의 최신 등록을 선택하는 저장 계약과 기존 ACCEPTANCE 일부 확인 수집/등록/재조회 연결은 다음 구현이다. 이 단계는 관측 파일을 선택해 현재 원본을 재대조하며 관측 실행 이력을 대신 판정하지 않는다. 외부 저장소/전체 변경 수집·회수/실회사10인·기기/최종전환/최종 PASS는 여전히 미완료다. 관측만 추가해 ready나 네 미확인 조건을 변경하지 않는다.

## 16. 회사 변경 기록 관측을 인수 일부 확인에 연결

41차의 단독 관측 파일은 그대로 운영 실행 기록에 올리지 않는다. 현재 DB 수집 경로에서 관측 원본을 함께 읽어 **진단v3 / CURRENT_REGISTERED_SOURCES_AND_JOURNAL**인 ACCEPTANCE 증거를 만든다. 기존 v1/v2 대조와 지문은 유지한다. 서명 관측·수집 발급의 회사/용도별 키를 분리하고, 회사 관리자 `admin`의 로그인 이름으로 서명 권한이나 GW 역할을 대신하지 않는다.

```sh
# §15의 새 서명 관측을 먼저 생성한다. 기존 비공개 실행 환경/키 설정을 사용한다.
# 여기서는 ACCEPTANCE_RECONCILIATION 발급 키를 지정한다(관측 개인키 불필요).
uv run --project backend python tools/gw_acceptance_collect.py \
  --current-company-id <회사ID> --signed-reconciliation \
  --journal-observation <0600_서명관측.json> --output <0700폴더의새인수증거.json>
```

현재 회사/활성 세대·정책·제품/DB·물리 DB·현재 신뢰 키와 15분 관측 기한을 대조한다. 관측 원본/서명을 외부 인수 서명 안에 보존하며, 관측 runId는 백업·복원·인수 runId와 달라야 한다. 백업·복원의 최신 등록 선택은 결과/정책/버전 성공 필터 없이 유지한다. 관측은 정상일 때도 PARTIAL이며, 관측 BLOCKED는 ACCEPTANCE FAIL/종료2로 보존한다. 정상 일부 확인은 종료0, 검증 오류/파일 오류는 종료1이다. 관측 옵션은 현재 DB 서명 수집에서만 쓸 수 있으며 파일 쌍 대조/사본 검사와 혼용하지 않는다. 출력은 새0600 파일이고 자동 등록은 하지 않는다.

증거 등록은 기존 보안 관리자·최근 본인 확인·현재 회사 잠금 경로를 그대로 사용한다. 새 인수 수집/등록 시 관측 시각이 **결과·정책·버전·원본 유무와 관계없이 가장 최근 등록한 ACCEPTANCE의 등록 시각보다 뒤**여야 한다. 이전 파일을 다시 서명해 새 실행으로 등록하는 우회를 막는다. 같은 회사/세대에 v3를 등록한 뒤에는 새 v1/v2나 관측 없는 인수 증거 등록을 거부한다. v1/v2 과거 기록 조회는 유지하며 새 세대에 이 규칙을 임의 전파하지 않는다. 등록된 관측의 원본과 결과는 기존 불변 운영 실행 이력에 보존하고, 준비 조회는 가장 최근 등록을 검증한다. 원본 없음·서명/행 변조·옛 정책/버전·최신 미통과를 과거 일부 확인으로 대체하지 않는다. 등록하지 않은 운영자 파일 전체의 실행 순서나 실패 이력을 아는 기능은 아니다.

**등록 자체가 만드는 변경 기록:** 인수 자료 등록도 암호화 회사 변경 기록을 남긴다. 따라서 관측한 끝 지문이 현재 체인의 보존된 접두부인지 확인한 뒤, 이후 기록은 같은 회사/세대의 정확한 `gw.operating_evidence.record` 동작·실DB 감사 확인·같은 물리 원본/타임라인의 거래 근거가 모두 있는 경우만 허용한다. 기록을 건너뛰거나 지우지 않는다. 다른 회사/core/업무 변경·취소/진행 중 등록·근거 누락은 새 관측을 요구한다. 관측 접두부의 감사/거래 상태와 집계도 현재 DB에서 다시 대조한다. 기록이 없는 빈 관측도 BLOCKED/FAIL이며 통과가 아니다.

수동 최신 지문 설정을 쓰면 증거 등록 뒤 생성된 **등록 영수증까지 검증한 최신 지문**으로 운영자가 별도 지문을 갱신해야 준비 재조회가 가능하다. 오래된 지문은 INVALID이며 자동으로 신뢰하지 않는다. 전달 확인 경로를 쓰면 기존 별도 전달·지문 검증 절차를 따른다. 이 연결은 별도 저장소 독립성이나 실외부 장애 복구를 보장하지 않는다. DB 관측/파일의 동시성을 무기한 보장하지 않으며, 관측/검증 도중 파일 변경은 거부하고 이후 변경은 다음 등록/준비 조회에서 차단한다.

운영 준비의 기존 **실행 증거 확인**에 현재 재대조가 된 관측만 시각·대상/감사 확인/거래 취소/미확인·근거 없는 건수와 다음 조치를 표시한다. 현재성을 잃으면 과거 집계를 정상 결과처럼 표시하지 않는다. 미확인 거래와 거래 근거 누락은 겹칠 수 있으므로 두 수를 합산하지 않는다. 화면 전체 구성의 최종 인수를 뜻하지 않는다.

최종 `ready=false`, 실제 복원 PARTIAL, 외부 저장소·전체 수집/권한 회수·실회사·최종 전환 4조건 UNVERIFIED와 ACCEPTANCE PASS 거부는 그대로다. 실환경 저장소/10인 인수·최종 전환 계약·최신 main 통합/전체 회귀는 별도 후속이다. DB 스키마를 추가하지 않고 기존 증거 JSON/불변 이력을 사용한다.

## 17. 복원 직후 제한 재대조 관측

기존 `gw_backup.py restore`는 제한 재적용 거래가 커밋된 뒤 **별도 READ ONLY/REPEATABLE READ 거래**에서 복원본을 다시 읽는다(문장15초/잠금3초). 이 관측을 통과해야 RESTORE PARTIAL을 발급한다. 새 옵션이나 사용자 체크로 통과시키지 않는다. 기존 복원 명령·비공개 접속/키·새 DB 생성·PUBLIC CONNECT 회수/접속수0 절차를 그대로 사용한다. 임의 회사 계정이나 개발 관리자 `admin`을 생성·이름 변경·승격하지 않는다.

- 공통 인증: 백업과 최신 권한 대조의 두 상태에 모두 허용된 계정 식별/자격 지문·보안 버전, 플랫폼 역할, 회사 멤버십, 인증 앱/OTP 재사용 방지 단계·복구 코드/SSO, 인증 시도 제한을 읽기 대조한다. 비활성화·회수처럼 더 강한 제한은 허용한다. 모든 세션의 회수와 PENDING 인증 요청 없음도 실제 DB에서 검사한다.
- GW: 두 상태의 활성 직원·조직 연결·역할/열람자·본인 연결을 대조한다. 기존 guard 차이와 변경 기록의 격리 범위는 활성 연결 없음/보존 중지를 확인하고, 위임의 회수도 확인한다.
- HR: 두 상태에서 허용되지 않은 근무 계정이나 변경 기록상 제한 대상의 활성 권한이 남았는지 HR 소유 어댑터로 대조한다. 새 교차 스키마 FK/업무 쓰기는 없다.

새 **복원 진단v2 / executionObservation / RESTORED_CHECKPOINT_RESTRICTIONS**는 백업·권한 대조 실행 번호와 명세/암호화 파일 지문, 원본/복원본 물리 식별 지문, 관측 시각·상태 지문, 접속 제한과 잔여 세션/인증 요청·불일치 집계를 RESTORE 서명 안에 묶는다. 실제 계정·자격 지문/MFA 원문·DB 접속/경로·원문 스냅샷은 제품 증거에 넣지 않는다. 상세 DB 이름은 기존 비공개 복원 보고서에만 남는다. 복원본은 원본과 다른 물리 DB 식별이어야 한다. 운영자와 DB 시계의 기존 허용 차이30초를 명시하며 허용 범위 밖 관측은 거부한다. 제품/DB 버전과 서명자의 실제 배포 소스까지 독립적으로 증명한 것은 아니다.

현재 등록된 복원 증거 전체의 지문을 기존 ACCEPTANCE 원본 참조에 묶으므로 이 관측도 인수 서명/최신 원본 재대조의 일부다. 추가로 관측의 backupRunId가 참조한 최신 BACKUP 실행 번호인지 확인한다. 변조·옛 정책/버전·최신 실패/원본 없는 등록은 이전 성공으로 대체하지 않는다. 기존 진단v1 원본과 과거 조회는 유지하고, 없는 관측값을 추정해 채우지 않는다. ACCEPTANCE 발급 키는 기존의 별도 용도를 유지하며 관측은 신뢰하는 RESTORE 실행자의 서명 아래에 있다. 독립 감사자의 별도 서명을 만든 것이 아니다.

관측에 잔여 권한/세션·진행 중 인증·접속 제한/DB 버전 불일치가 있으면 BLOCKED다. 측정을 마친 BLOCKED는 서명 RESTORE FAIL과 비공개 FAIL 보고를 남기며 새 복원본의 연결을 추가 차단한다. 제한 적용 함수가 성공 표지를 반환해도 재대조 실패는 PARTIAL로 서명하지 않는다. 관측 전에 실패했거나 실제 측정 자체가 불가능하면 기존 실패/격리 보고만 남기고 관측을 지어내 서명하지 않는다. 실패 시 생성한 복원본은 자동으로 열거나 지우지 않는다. 준비 화면은 등록된 최신 실패를 유지하며, 자동 등록하지 않은 도구 실패 전체를 서버가 아는 기능은 아니다.

운영 준비의 **최근 복원 검사 내용 → 복원 직후 제한 재대조**에서 관측 시각·남은 세션/인증 요청·제한 불일치를 읽는다. 이는 서명된 실행 시점의 관측이며 현재 복원본을 제품 API가 다시 조회한 결과가 아니다(`currentTargetStateVerified=false`). 관측 후 복원본의 권한/격리 상태가 달라졌는지 재검증하는 별도 어댑터는 후속이다. PUBLIC CONNECT/접속수0은 일반 접속 제한이며 superuser·운영 앱/worker·네트워크 차단 전체를 증명하지 않는다.

모든 집계가0이어도 PARTIAL이며 `revocationsComplete`, `revocationsReapplied`, `checkpointCompletenessConfirmed`, `twoAccountChecks`, `ready`를 완료로 바꾸지 않는다. 외부 저장소·전체 변경 수집/권한 회수·실회사/기기·최종 전환4조건은 미확인이다. 실제 회사10인 인수와 최신main/전체 회귀·최종 PASS 계약은 별도로 남는다. 스키마/마이그레이션/Excel/ERD 변경 없음.


## 18. 기존 격리 복원본의 신선한 읽기 재관측 (44차)

- 기존 `tools/gw_backup.py recheck-restore`는 새 복원을 만들거나 기존 복원본의 접근 제한을 바꾸지 않는다. 전용 `FS_GW_RECHECK_DATABASE_URL`의 `fs_gw_restore_<UUID32>_test`만 읽는다. 일반 `DATABASE_URL`이나 관리자 URL을 자동 대체하지 않는다. 실제 운영 DB/계정으로 시험하지 않는다.
- 원본 BACKUP 암호화 묶음, CHECKPOINT와 별도 서명 HEAD/기대 지문, 서명 RESTORE 진단v2 원본이 필요하다. 전체 명세/파일 지문·실행 번호·회사/세대/정책/제품/DB 버전을 대조한 뒤 READ ONLY/REPEATABLE READ 거래에서 물리 복원본 식별을 먼저 확인하고 제한·세션·인증 요청을 다시 읽는다. 다른 물리 DB는 출력 없이 거부한다.
- 새 RESTORE_RECHECK 회사/용도 범위의 발급 키를 사용한다. ACCEPTANCE_RECONCILIATION 발급 키는 별도로 유지한다. 비공개 키와 URL을 명령행/채팅/Git에 적지 않는다. 기존 보안 설정과 신뢰 공개 키도 필요하다. 출력은0700 폴더 안의 새0600 파일이며 덮어쓰지 않는다.

```sh
# 환경 변수는 별도 비공개 실행 환경에 주입한다. 예시 경로는 모두 합성이다.
uv run --project backend python tools/gw_backup.py recheck-restore \
  --backup /private/gw/database.fsbackup \
  --checkpoint /private/gw/latest.fsbackup --head /private/gw/head.json \
  --expected-checkpoint-digest "$GW_CHECKPOINT_DIGEST" \
  --restore-evidence /private/gw/restore.json --output /private/gw/recheck-new.json
# 별도 ACCEPTANCE 발급 키와 원본 회사용 FS_GW_PREFLIGHT_DATABASE_URL로 전환 후:
uv run --project backend python tools/gw_acceptance_collect.py \
  --current-company-id 3 --signed-reconciliation \
  --restore-recheck /private/gw/recheck-new.json --output /private/gw/acceptance-new.json
```

- 제한 대조가 명확한 경우에도 재관측 PARTIAL/종료0이다. 잔여 세션/권한·공개 접속/접속수 제한 불일치는 BLOCKED/종료2이며 ACCEPTANCE FAIL로 연결한다. 연결/권한/스키마 오류는 measurement=null/targetMeasured=false로 서명하고 미통과로 남긴다. 도구는 연결을 열거나 제한을 재적용하지 않는다. 사전 계약/다른 물리 대상 오류는 종료1/출력 없음이다.
- 서명 관측은 최대15분, 미래 허용30초이며 단일 시점의 일부 확인이다. `stateMatchesExecution`은 상태 지문 일치 여부이고 불일치만으로 권한이 늘었다고 단정하지 않는다. 새 제한 대조가 명확해도 전체 회수·실회사/전환 확인은 false다. 원래 권한 대조 이후 발생한 미수집 변경의 완전성을 증명하지 않는다.
- 수집기는 최신 등록 BACKUP/RESTORE 전체 원본을 다시 선택해 ACCEPTANCE 진단v4에 재관측 문서를 연결한다. `--journal-observation`도 함께 사용할 수 있다. 한번 등록한 관측 유형은 새 등록에서 생략할 수 없고, 새 관측 시각은 최신 ACCEPTANCE 등록 시각보다 뒤여야 한다. 같은 관측 실행 번호의 재사용도 거부한다. 실행자/DB 시계 차이로 등록 시각을 아직 넘지 못하면 시계를 확인하고 그 이후 새 관측으로 재시도한다. 실패·다른 정책·원본 없는 이력도 유형 유지 판단에 포함한다. 원본 없는 기록/최신 실패·변조·옛 정책/제품·기한 경과를 과거 성공으로 대체하지 않는다.
- 파일을 도구로 만들었다고 자동 등록되지 않는다. 재관측 단독 문서는 제품 실행 증거 API가400으로 거부한다. 기존 관리자 화면에서 수집기가 만든 ACCEPTANCE를 등록하고 최근 결과/관측 시각/측정 여부를 확인한다. 서버는 서명/원본을 검증하며 복원 DB에 직접 접속하거나 연속 감시하지 않는다. `admin` 로그인 이름은 보안 권한이나 발급 키 권한을 부여하지 않는다.
- ready=false, 실제 복원 PARTIAL, 최종4조건 UNVERIFIED 유지. 외부 공급자 선정·실제 외부 장애복구·전체 변경 회수 완전성·실회사10인·최종 전환은 아직 남아 있다.


## 19. 현재 원본과 복원 권한 대조의 읽기 비교 (45차)

기존 `recheck-restore`에 `--check-current-source`를 추가하고, 별도 비공개 환경 `FS_GW_SOURCE_CHECKPOINT_DATABASE_URL`에 원래 백업의 원본 접속을 주입한다. 복원본은 기존 `FS_GW_RECHECK_DATABASE_URL`을 유지한다. 두 접속을 자동 교환하거나 일반 DATABASE_URL로 대체하지 않는다. 새 원본 비교도 명시적 회사/RESTORE_RECHECK 키와 별도 ACCEPTANCE 발급 키를 사용한다.

```sh
# 두 전용 URL/암호화 키/발급 키는 비공개 실행 환경에 주입한다.
uv run --project backend python tools/gw_backup.py recheck-restore \
  --check-current-source --backup /private/gw/database.fsbackup \
  --checkpoint /private/gw/latest.fsbackup --head /private/gw/head.json \
  --expected-checkpoint-digest "$GW_CHECKPOINT_DIGEST" \
  --restore-evidence /private/gw/restore.json --output /private/gw/source-recheck-new.json
# 별도 인수 발급 키로 전환 후 §18과 같은 현재 DB 수집 명령을 사용한다.
uv run --project backend python tools/gw_acceptance_collect.py \
  --current-company-id 3 --signed-reconciliation \
  --restore-recheck /private/gw/source-recheck-new.json --output /private/gw/source-acceptance-new.json
```

- 원본 어댑터는 새 READ ONLY/REPEATABLE READ 거래에서 물리 원본 식별을 먼저 대조하고 현재 회사/세대/정책·DB head와 core/GW/HR의 **체크포인트 수집 항목**을 읽는다. 쿼리 행 순서를 정규화한 지문과 묶음별 변경 수를 원래 권한 대조 내용과 비교한다. 다른 물리 원본은 수집/출력 없이 거부한다. 개인/계정/권한/자격 원문은 서명 요약으로 내보내지 않는다. 이 백업의 전역 보안 스냅샷 범위이므로 같은 물리 DB의 다른 회사·공간 변경도 차단할 수 있다.
- 새 RESTORE_RECHECK v2는 현재 원본 관측과 기존 복원본 제한 관측을 한 서명에 담는다. sourceObservation의 관측 시각/기대 물리 원본·권한 대조 상태 지문/현재 지문/기준 일치/변경 묶음/측정 여부를 포함한다. 두 관측과 발급 시각은30초 이내이고 원본 관측도 별도로15분 기한·미래30초를 검사한다. 기존 인수 진단v4에 그대로 연결하며 새 스키마/인수 종류는 만들지 않는다.
- 원본 수집 항목·기준이 달라졌다면 복원본 관측이 PARTIAL이어도 재관측은 BLOCKED/종료2, 인수는 FAIL이다. 원본을 읽지 못하면 sourceMeasured=false, 지문/변경 묶음/기준 일치는 null이며 변경 없음으로 추정하지 않는다. 다른 물리 대상·명세/파일/서명·시계 계약 오류는 출력 없이 종료1이다. 원본/복원본의 권한 변경·연결 개방·재생/새 복원은 이 명령이 하지 않는다. 일치도 PARTIAL/종료0이며 운영 승인이 아니다.
- 원본 비교를 한번 등록했다면 이후 새 등록에서 이전 v1/원본 비교 없는 관측으로 되돌릴 수 없다. 최신 인수 등록 이후의 원본 관측도 요구하며 기존 관측 실행 번호 재사용/기존 유형 생략 금지를 유지한다. 이력의 실패·옛 정책·원본 없는 행도 포함한다. 수집기를 우회해 발급한 파일도 서버 등록에서 같은 금지를 검사한다. 새 권한 대조 파일이 있더라도 옛 RESTORE 원본과 섞을 수 없다. 변경 원인을 확인한 뒤 새 권한 대조와 새 격리 복원으로 다시 점검한다.
- 서버는 서명/원본·현재 정책/버전/최신 등록을 재검증하며, 원본/복원본을 직접 또는 연속 감시하지 않는다. 정책/DB head 일치와 운영자가 입력한 제품 버전 연결은 실행 바이너리 증명을 뜻하지 않는다. 체크포인트에 없는 원본 세션/추가 경로와 두 시점 사이 변경 후 원복, 외부 HEAD 목록의 독립 최신성·전체 변경 수집/권한 회수 완전성은 증명하지 않는다.
- 기존 화면의 실행 증거 → 복원본 최근 재관측에서 비교 시각·공통/GW/인사 변경 묶음·측정 불가·다음 조치를 읽는다. 이전 기록에 이 비교가 없으면 추정하지 않는다. admin 이름은 권한을 대신하지 않는다. 실제 복원 PARTIAL/ready=false/최종4조건 UNVERIFIED 유지. 실제 외부 공급자·장애복구·실회사10인·main/전체회귀·최종 인수는 후속이다.


## 20. 원본 변경 실패 이후 새 대조·격리 복원·후속 인수 (46차)

이 흐름은 운영 재개나 전체 인수 승인이 아니다. 같은 회사/세대의 원본 변경(CHANGED) ACCEPTANCE FAIL을 기준으로 이후 새 PARTIAL 등록을 제한한다. 실패 기준은 모든 정책·버전에서 최근 등록 순으로 선택하고, 각 종류의 현재 증거는 기존처럼 실패/미확인/원본 없는 기록도 포함해 최신 하나만 선택한다. 두 선택을 과거 성공 검색으로 대체하지 않는다.

1. 원본 변경의 원인을 확인한다. 과거 실패의 서명 원문과 등록 행을 재대조한다. 현재 키의 회사/용도 권한, 인수 외부 서명과 내부 재관측 서명·등록 메타데이터/집계를 대조하며 원문 없음/변조/키 회수/복원 관측 없음은 새 백업 요구로 남긴다. 역사 원본의 서명 확인은 현재 정책/버전/15분 관측의 통과가 아니다.
2. 정상 원본을 준비한 뒤 기존 `checkpoint`로 **다른 권한 대조 실행/파일**을 만든다. 이전 실패 원본/복원 관측을 확인할 수 없거나 현재 백업이 유효하지 않으면 새 BACKUP부터 만들고 등록한다. 이 경우 새 백업 시작 시각은 실패 등록 시각보다 뒤여야 한다. 현재 정책/제품/DB 버전 불일치도 기존 현재성 검사로 차단된다.
3. 기존 `restore`로 **새 물리 격리 복원 DB**를 만든다. 실패 등록 이후에 시작한 다른 RESTORE 실행이어야 하며, 검증 가능한 실패 원본이 있으면 과거 대상 식별과 권한 대조 runId/암호화 파일 지문도 모두 달라야 한다. 새 대상도 기존 PUBLIC CONNECT 회수·접속수0/제한·세션 회수를 유지한다. 서명 RESTORE 원본을 기존 관리자 화면에 등록한다. 원본 변경을 되돌린 뒤 옛 복원본만 다시 관측하거나, 새 물리 DB에 같은 체크포인트를 재사용한 결과로 새 PARTIAL을 등록할 수 없다.
4. §19의 `--check-current-source`로 현재 원본과 새 복원본을 읽고, §18의 현재 DB 수집기로 인수 점검을 발급한다. 별도 회사/RESTORE_RECHECK 키와 ACCEPTANCE_RECONCILIATION 키를 사용하며 필요한 JOURNAL_OBSERVATION도 유지한다. 최신 등록 이후의 새 관측과 기존 형식 생략/실행 재사용 금지는 그대로다. 새 권한 대조·복원·관측이 있어도 결과는 PARTIAL이며 PASS는 여전히 거부한다.
5. 새 ACCEPTANCE를 등록한 뒤 기존 **원본 변경 후 재점검**에서 현재 단계/기준 실패 등록 시각/다음 조치를 확인한다. 새 복원 연결은 RECHECK_REQUIRED, 현재 원본 일치·새 복원본을 참조한 인수 일부 확인은 RECOVERY_PARTIAL이다. 기준 실패는 삭제·수정하지 않는다. 더 최근 복원 실패·서명/원본 불일치·관측 만료가 있으면 이전 일부 확인으로 복구를 완료 처리하지 않는다.

```sh
# 비공개 환경의 기존 BACKUP/CHECKPOINT 발급 키와 원본 접속을 사용한다.
# 실패 원본이 없으면 먼저 새 backup을 만들고 서명 BACKUP을 등록한다.
uv run --project backend python tools/gw_backup.py checkpoint \
  --backup /private/gw/database.fsbackup --output /private/gw/recovery.fsbackup \
  --head /private/gw/recovery-head.json
# 기대 지문은 이 새 대조 파일의 별도 최신 지문 확인 결과를 비공개 환경에 주입한다.
uv run --project backend python tools/gw_backup.py restore \
  --backup /private/gw/database.fsbackup --checkpoint /private/gw/recovery.fsbackup \
  --head /private/gw/recovery-head.json --expected-checkpoint-digest "$GW_CHECKPOINT_DIGEST" \
  --report /private/gw/recovery-report-new.json --evidence /private/gw/recovery-restore-new.json
# 새 RESTORE를 기존 화면에 등록한 뒤, §19의 재관측과 현재 DB 인수 수집을 새 파일로 실행한다.
```

명령은 원격 운영에 자동 실행되지 않는다. 새 대상 접속은 비공개 결과를 확인해 전용 환경에 주입하며, 기존 DB에 덮어쓰거나 미리보기 DB를 시험 초기화하지 않는다. 새 PARTIAL의 API 등록은 회사 잠금 안에서 이 복구 조건을 다시 대조하고, 수집기는 읽기 스냅샷에서 같은 조건을 검사한다. 조건 불충족은 OPERATING_RECOVERY_REQUIRED/400, 수집기 종료1·새 파일 없음과 다음 조치를 반환한다. FAIL 기록은 새 복원 조건을 이유로 거부하지 않아 반복 실패도 보존한다. CLI 키/URL/원문을 오류 출력에 넣지 않는다.

46차는 다른 권한 대조의 실행/파일 지문과 실패 등록 이후 새 복원 시작을 대조했다. 47차의 §21은 서명 HEAD의 생성 시각도 실패 등록 이후인지 추가 대조한다. 별도 최신 목록·독립 시각/실행 바이너리·연속 관측 증명은 후속이다. 실행자/DB 시계 차이 때문에 실패 등록 이후 시각을 충족하지 못하면 시계를 확인한 뒤 새 실행으로 재시도하며 순서 조건을 느슨하게 바꾸지 않는다. 새 서명 종류/DB 테이블/수동 완료 체크는 없다. 실제 복원 PARTIAL·ready=false·최종4조건 UNVERIFIED를 유지한다.


## 21. 권한 대조 생성 시각과 서명 HEAD 연결 (47차)

§19의 `recheck-restore --check-current-source`는 이제 RESTORE_RECHECK v3를 발급한다. 기존 명령·전용 원본/복원본 URL·비공개 파일 규칙은 그대로이며 새 옵션이나 DB 테이블은 없다. `--head`의 원본 `{payload,signature,signerKeyId}`를 `checkpointHead`로 포함한다. 원본 비교 없는 재관측은 기존 v1을 유지한다.

- 재관측 실행 키의 RESTORE_RECHECK 권한과 별도로, HEAD 서명 키의 현재 회사/CHECKPOINT 권한과 기존 `FS-OPERATOR-BUNDLE-v1` 서명 문맥을 검증한다. 회사/세대/정책, 백업 실행·대조 실행·암호화 파일 지문을 원본 RESTORE 관측과 대조한다. 도구는 복호화한 대조 명세의 capturedAt과 HEAD도 대조한다. raw 보안 스냅샷이나 URL/개인키를 인수 증거에 넣지 않는다.
- capturedAt은 복원 시작보다30초 넘게 늦거나 복원 시작 기준 RPO+30초보다 오래될 수 없다. 이는 기존 DB/실행자 시계 허용 범위다. 원본 변경 FAIL 이후 후속 PARTIAL에는 **실패 등록 시각보다 엄격히 뒤에 생성한** 대조와 새 격리 복원이 필요하다. 다른 실행 번호/파일이어도 실패 전에 생성했으면 수집/등록/준비 재대조에서 거부한다. 이 순서에는30초 유예를 적용하지 않는다. 시계 차이로 충족하지 못하면 시계를 확인하고 새 대조부터 실행한다.
- 같은 회사/세대에 v3가 등록된 뒤에는 HEAD를 뺀 v2/v1으로 새 인수를 등록할 수 없다. 모든 정책/버전·실패/원문 없는 이력을 포함한다. 현재 HEAD 키의 CHECKPOINT 권한 회수·변조·원본 불일치는 기존 등록 인수도 INVALID로 만들며 과거 성공을 찾지 않는다. 구형 원본의 서명 바이트/지문을 수정하거나 누락된 HEAD를 추정하지 않는다.
- 기존 **복원본 최근 재관측 → 복원 권한 대조 생성 근거**는 서명·현재 원본 대조에 성공한 기록에서 생성 시각을 표시한다. 서명/현재 대조에 실패하면 이 요약은 표시하지 않는다. 대조 생성 시각이 확인돼도 **독립된 최신 HEAD 목록은 미확인**이다.

HEAD는 허가된 실행자가 서명한 생성 시각과 특정 파일의 연결 근거다. 별도 사람/장애 영역·불변 최신 목록/삭제 탐지·연속 관측·실행 바이너리/공인 시각 증명이 아니다. 같은 실행자가 BACKUP/RESTORE/CHECKPOINT 용도를 가질 수 있으며 기술적 재관측/인수 키 분리만으로 보관 독립성을 주장하지 않는다. 운영자가 고른 옛 HEAD와 기대 지문을 함께 제시하는 경우를 독립 목록으로 탐지하는 어댑터는 다음 작업이다. 외부 공급자는 미정이며 임의 선택하지 않았다. 실제 복원 PARTIAL/ready=false/최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부를 유지한다.


## 22. 별도 서명 목록의 현재 HEAD 대조 (48차)

이 단계는 **서버 설정에 고정한 별도 서명 목록**을 읽는 공통 어댑터다. 실제 외부 저장소 공급자/장애 영역·발행 담당자의 독립성·미수집 변경의 존재는 아직 인수하지 않았다. 별도 서명 키나 파일 하나만으로 외부 보관 완료를 선언하지 않는다. 목록 발행·불변 보관/교체 도구와 공급자별 수집은 후속이다. 이번 실제 DB 시험의 목록은 별도 시험 키가 발행한 합성 서명 자료다.

### 설정과 서명 권한

- 목록 발행자는 새 `CHECKPOINT_CATALOG` 용도만 갖는 키를 사용한다. `FS_GW_EVIDENCE_PUBLIC_KEYS`와 기존 v1 `FS_GW_EVIDENCE_KEY_SCOPES`에서 명시적으로 회사 ID를 허용한다. 이 키는 BACKUP/RESTORE/CHECKPOINT/RESTORE_RECHECK/ACCEPTANCE_RECONCILIATION 등 다른 용도와 혼용할 수 없으며 같은 공개키 바이트를 다른 이름으로 재사용할 수 없다. 인수 발급 키의 기존 분리도 유지한다. `admin` 로그인 이름/GW 보안 역할은 이 서명 권한을 대신하지 않는다.
- 서버와 읽기 도구의 운영자 소유 환경에 `FS_GW_CHECKPOINT_CATALOG` JSON을 지정한다. 정확한 필드는 `version`(정수1), `provider`(`SIGNED_SNAPSHOT_FILE`), `catalogId`(정규 UUID4), `file`(절대 경로), `digest`(목록 문서 파일 **전체 바이트**의 소문자 SHA-256)다. 알 수 없는 필드·중복 JSON 키·빈 설정·상대 경로는 거부한다. 목록 식별자/기대 지문은 선택한 HEAD/백업 도구의 입력값에서 자동 복사하지 말고 별도 목록 발행 경로에서 확인한다. 서명 입력 파일이나 API 요청으로 이 경로/신뢰 핀을 바꿀 수 없다.
- 각 실행 환경에서 파일은 실행 계정 소유0600 일반 파일, 직접 부모 폴더는0700이어야 한다. 마지막 파일/부모의 심볼릭 링크·다른 소유자·권한 과다·2MiB 초과를 거부한다. 서버/도구가 다른 OS 계정이면 각자 소유한 비공개 사본에 동일한 고정 지문을 적용한다. 어댑터는 새 파일을 발행하거나 기존 목록·정책·계정·복원 제한을 변경하지 않는다.

### 목록 원본 계약

문서 최상위는 정확히 `{envelope,signature}`다. envelope의 필드는 `version`(정수1), `kind`(`CHECKPOINT_CATALOG`), `catalogId`, `revision`(양의 정수, 최대 int64), `publishedAt`(시간대 포함 시각), `records`(0~1000개), `signerKeyId`다. signature는 해당 키가 `b"FS-GW-CHECKPOINT-CATALOG-v1\0" + canonical(envelope)`를 Ed25519로 서명한 표준 base64다. canonical은 기존 운영 계약의 UTF-8/키 정렬/공백 없는 JSON/NaN 금지를 사용한다. 파일 지문에는 문서의 실제 개행도 포함된다.

각 records 항목은 정확히 `sequence`(목록 안에서 중복 없는 양의 int64), `workspaceId`/`generationId`(양의 정수 문자열), `policyDigest`, `codeRevision`, `dbRevision`, `recordedAt`, `result`(`PASS`/`PARTIAL`/`FAIL`), `head`(기존 `{payload,signature,signerKeyId}` CHECKPOINT_HEAD 또는 null)다. head가 있으면 회사/세대/정책과 기록 시각을 대조하고, 선택된 최신 head의 현재 CHECKPOINT 키 권한/원본 서명도 확인한다. 목록 결과는 발행자가 서명한 목록 원본 상태이며 복원 도구가 실제 실패를 측정했다거나 전체 인수가 통과했다는 뜻은 아니다.

목록 발행 시각의 기한은15분/미래30초다. 항목 등록 시각은 발행보다30초 넘게 늦을 수 없으며 head 생성도 등록보다30초 넘게 늦을 수 없다. 시계 동기·발행 주기/신뢰 지문 전달은 실제 운영 인수 대상이다. 서버는 현재 핀과 원본 서명을 검사하며 일반 DB 접속이나 입력 HEAD로 목록을 대체하지 않는다.

### 기존 도구와 인수 연결

```sh
# 비공개 환경에 현재 목록 설정과 기존 원본/복원본 전용 URL·RESTORE_RECHECK 키를 주입한다.
uv run --project backend python tools/gw_backup.py recheck-restore \
  --check-current-source --check-checkpoint-catalog \
  --backup /private/gw/database.fsbackup --checkpoint /private/gw/latest.fsbackup \
  --head /private/gw/head.json --expected-checkpoint-digest "$GW_CHECKPOINT_DIGEST" \
  --restore-evidence /private/gw/restore.json --output /private/gw/catalog-recheck-new.json
# 별도 ACCEPTANCE_RECONCILIATION 키와 현재 DB 전용 읽기 URL로 전환한다.
uv run --project backend python tools/gw_acceptance_collect.py \
  --current-company-id 3 --signed-reconciliation \
  --restore-recheck /private/gw/catalog-recheck-new.json --output /private/gw/catalog-acceptance-new.json
```

- 명시 옵션은 목록 설정 누락을 오류로 처리한다. 설정이 있으면 옵션을 생략해도 목록을 대조하며 `--check-current-source`가 필요하다. 일반 DATABASE_URL 자동 대체·원본 비교/목록 대조 생략은 없다. 새 재관측은 **RESTORE_RECHECK v4**, 기존 인수 진단은 그대로 v4다. 원본 HEAD와 현재 목록 지문/식별자·버전/발행/관측 시각·선택한 최신 기록 번호/결과·HEAD 지문/생성 시각·대조 이유를 서명한다. 전체 목록/다른 회사 항목·경로/URL·개인키는 인수 증거에 넣지 않는다.
- 선택 회사/세대의 `sequence`가 가장 큰 항목 하나를 모든 정책·제품/DB 버전·결과/원문 유무에서 선택한다. 최신 FAIL/PARTIAL·원문 없음·회사/세대 기록 없음·현재 기준 불일치·선택 HEAD 불일치는 BLOCKED→ACCEPTANCE FAIL이다. 과거 PASS를 찾지 않는다. 파일/서명/권한/핀·형식/기한 오류에는 출력 없이 종료1이며 값을 지어내지 않는다. 정상 일치도 PARTIAL/종료0, 목록 미통과는 재관측 BLOCKED/수집 FAIL·각 종료2다. 수집기는 자동 등록하지 않는다. v4 재관측 단독 API 업로드는400이다.
- 현재 DB 수집·회사 잠금 안 API 등록·준비 재조회 때 현재 설정의 목록을 다시 읽어 서명 관측과 대조한다. 수집 후 목록/핀·키 권한이 바뀌면 기존 인수는 INVALID가 되고 상세 요약을 숨긴다. 설정 중에는 기존 목록 없는 인수도 거부한다. v4 등록 이후 설정을 제거해도 구형 형식으로 새 인수를 등록할 수 없다. 형식/이력 규칙은 모든 정책/실패/원문 없는 행을 포함한다.
- 기존 등록 이력의 식별자·목록 버전/기록 번호·HEAD 지문/생성 시각을 바닥값으로 사용한다. 식별자 리셋, 버전/기록 번호 후퇴, 같은 버전의 다른 파일 지문, 같은 번호의 다른 HEAD/결과, 새 번호로 옛 생성 시각/다른 HEAD를 제시하는 새 PARTIAL을 거부한다. 목록 대조가 미통과였다면 그 실패 등록 이후 생성한 새 대조와 격리 복원을 요구한다. 목록 번호만 높인 옛 성공으로 복구할 수 없다. 순서에는30초 유예를 적용하지 않는다. 바닥값인 관측 자체를 재구성할 수 없는 손상 이력은 차단하며, 이를 지우거나 임의로 초기화하는 도구는 제공하지 않는다.
- 기존 **복원본 최근 재관측 → 별도 서명 목록 대조**에서 관측 시각·목록 버전/최신 번호·일치/최신 실패·미확인 범위와 조치를 읽는다. 목록이 바뀌어 이전 관측을 재검증할 수 없으면 이전 상세로 대신하지 않는다. 화면 전체 완성이나 실제 API 브라우저·실회사10인 인수는 별도다.

이 어댑터는 확인 시점에 설정된 서명 스냅샷을 대조한다. 외부 발행과 DB 등록 사이를 하나의 원자 거래로 만들거나 원격 목록을 연속 감시하지 않는다. 서버가 아직 관측하지 못한 더 최신 기록·숨겨진 기록, 발행자 자체의 악의/누락·물리 재해 분리·미등록 이력 전체/실행 바이너리·공인 시각을 증명하지 않는다. 보관/키 독립성은 `externalIndependenceVerified=false`, 최종4조건은 UNVERIFIED이며 실제 복원 PARTIAL·ready=false·ACCEPTANCE PASS 거부를 유지한다. 공급자는 미정이며 원격 연결/배포를 임의 설치하지 않았다. 다음은 이 계약을 따르는 목록 발행·불변 교체/신뢰 핀 전달 도구와 장애 검증이다.

## 23. 로컬 서명 목록 발행·원자적 핀 교체 (49차)

§22의 정적 JSON 핀 모드는 유지한다. 새 `tools/gw_checkpoint_catalog.py`는 **회사/세대 하나의 운영자 소유 로컬 폴더**에 목록을 발행한다. 실제 외부 공급자·다른 OS 계정의 수신/전달·누락 버전 따라잡기는 아직 제공하지 않는다. 이 도구가 과거 파일을 덮어쓰지 않는 것은 OS/공급자 WORM이나 물리 독립 보관 증명이 아니다. 실제 저장소/미리보기 설정을 자동 설치하지 않는다.

### 발행 담당자 준비

- 목록 전용0700 절대 폴더를 비워서 준비한다. 백업·대조 입력과 다른 전용 폴더를 사용한다. `.catalog.lock`은 재사용하므로 임의 삭제하지 않는다. 최초 발행만 `--initialize --expected-pin-digest ABSENT`를 명시한다. 기존 핀/파일/보류 발행이 있는 폴더를 최초 상태로 간주하지 않는다.
- 발행 환경의 `FS_GW_CATALOG_KEY_FILE`은 소유자0600인 Ed25519 개인키32바이트 파일, `FS_GW_CATALOG_KEY_ID`는 §22의 회사/CHECKPOINT_CATALOG 단독 용도 허용 키다. 현재 공개키와 개인키도 대조한다. 읽기 서버에 개인키가 필요하지 않다. 기존 실행자/인수 키나 `admin` 로그인 이름으로 대신하지 않는다.
- `--context`는0700 부모 안0600 JSON이며 정확히 `workspaceId`/`generationId`(양의 정수), `policy`(현재 운영 정책 전체), `codeRevision`/`dbRevision`을 담는다. 발행자는 현재 회사/정책/버전을 별도로 확인한다. 도구는 DB에서 이 값을 자동 수집하거나 실행 바이너리를 인증하지 않는다.
- `--head`는 기존 도구의 서명 HEAD, `--checkpoint`는 그 HEAD에 대응하는 실제 암호화 대조 파일이다. 소유자/비공개 일반 파일·링크/하드링크·중복 JSON·형식/크기·현재 회사/CHECKPOINT 키 서명·세대/정책·RPO+30초/미래30초·전체 파일 SHA-256·읽기 중 파일 변경을 검사한다. 암호화 형식 헤더/지문 대조이며 이 발행 단계가 복호화·복원 결과까지 증명하지 않는다.

```sh
uv run --project backend python tools/gw_checkpoint_catalog.py publish \
  --directory /private/gw-catalog --context /private/gw-input/context.json \
  --head /private/gw-checkpoint/head.json --checkpoint /private/gw-checkpoint/latest.fsbackup \
  --initialize --expected-pin-digest ABSENT
# 후속 명령의 예상 지문은 status 결과와 담당자가 보관한 이전 전달 기록을 대조한다.
uv run --project backend python tools/gw_checkpoint_catalog.py status \
  --directory /private/gw-catalog --context /private/gw-input/context.json
uv run --project backend python tools/gw_checkpoint_catalog.py refresh \
  --directory /private/gw-catalog --context /private/gw-input/context.json \
  --expected-pin-digest "$GW_CATALOG_PIN_DIGEST"
```

출력은 목록 식별자/버전·번호/결과, 목록 파일 전체 지문과 핀 파일 지문·`ready=false` 등 제한된 진단이다. 개인키·접속 정보·전체 문서/파일 경로를 출력하지 않는다. **catalogDigest와 pinDigest는 다른 지문**이다. 발행 경합 검사는 `pinDigest`를 사용한다. `status`는 무결성/현재 버전과 보류 상태를 조회하는 명령이며 목록 발행 시각의15분 기한이나 운영 준비를 통과시키는 명령이 아니다.

### 발행 결과와 중단 처리

- 정상 대조는 목록 항목 PASS/종료0이다. **목록 파일 대조의 PASS이며 ACCEPTANCE PASS나 운영 승인과 무관하다.** 권한/문맥/예상 핀을 확인한 뒤 원본 검증이 실패하면 새 FAIL·원문 null/종료2를 발행한다. 최신 실패를 이전 성공으로 대신하지 않는다. 권한·핀·기존 목록/폴더 오류는 종료1이며 자동 초기화하지 않는다. 실패 원인 원문이나 민감한 파일 내용을 로그로 출력하지 않는다.
- 각 발행은 전체 바이트 지문을 이름에 넣은 새0600 `catalog-<20자리 revision>-<sha256>.json`을 생성하고 fsync한다. 현재 스냅샷에는 최신 항목 하나만 담고, 과거 스냅샷·FAIL·불완전 파일은 보존한다. 폴더 항목은 최대100,000개이며 초과 시 차단한다. 장기 보관/이관·용량 관리 도구는 후속이며 임의 삭제로 우회하지 않는다. 목록 식별자는 유지하며 새 기록은 번호를 증가시킨다. `refresh`는 버전/발행 시각만 새로 서명하고 이전 항목의 번호/시각/결과/HEAD/기준을 그대로 보존한다. FAIL/PARTIAL을 PASS로 바꾸거나 옛 정책을 새 정책으로 꾸미지 않는다.
- 전용 잠금과 예상 핀 지문을 함께 검사한다. 같은 예상 핀으로 경합하면 한 발행만 진행한다. 의도 기록 `.catalog.pending`을 **원본 파일 읽기 전에**0600 생성/fsync하고, 새 스냅샷과 임시 핀을 fsync한 뒤 `current-pin.json`을 같은 폴더 안 원자 교체·폴더 fsync한다. 완료 후에만 보류 기록을 제거/fsync한다. 동일 OS 소유자의 악의적인 우회 쓰기를 막는 WORM/CAS 서비스는 아니다.
- 중단/쓰기 실패/완료 응답 유실 시 먼저 `status`를 확인한다. 보류 기록이나 현재 핀보다 높은 저장 버전이 있으면 관리 핀 읽기는 차단된다. 이전 핀으로 자동 롤백하거나 불완전 파일을 삭제하지 않는다. 핀이 이미 교체됐더라도 보류가 있으면 차단한다.
- 유효한 보류 기록과 재검증 가능한 현재 핀이 있을 때만 다음 명령을 사용한다. 예상 핀은 중단 전 값이 아니라 **현재 status의 지문**이며 최초 중단으로 핀이 없으면 ABSENT다. 복구는 원래 시도한 PASS를 활성화하지 않고, 가장 높은 저장/예약 버전보다 높은 **새 PARTIAL·원문 null**을 서명한다. 보류/현재 핀 자체가 손상됐으면 자동 복구하지 않고 차단한다. 회사/세대 리셋·손상 이력 삭제 기능은 없다.

```sh
uv run --project backend python tools/gw_checkpoint_catalog.py recover-pending \
  --directory /private/gw-catalog --context /private/gw-input/context.json \
  --expected-pin-digest "$GW_CATALOG_CURRENT_PIN_DIGEST"
```

PARTIAL 복구/FAIL 이후에는 해당 기록 시각보다 엄격히 뒤에 생성한 새 대조가 필요하다. 옛 HEAD를 재발행하면 새 FAIL을 남긴다. 인수 API에 등록한 실패가 더 늦으면 §22의 실패 등록 이후 생성·새 격리 복원 조건도 별도로 적용한다. 파일 번호/발행 시각만 높여 복구하지 않는다.

### 기존 서버/도구의 관리 핀 읽기

운영자가 확인한 로컬 발행 폴더를 읽는 환경에 `FS_GW_CHECKPOINT_CATALOG_PIN_FILE=/private/gw-catalog/current-pin.json`을 설정할 수 있다. 기존 `FS_GW_CHECKPOINT_CATALOG` JSON과 **동시에 지정하거나 빈 값으로 지정하면 오류**다. 핀은 기존 v1 JSON이며 같은 폴더의 지문 이름 파일만 가리킨다. 읽기는 소유자/0700·0600/링크·서명/범위/15분·미래30초와 보류/최고 버전/읽기 중 핀 교체를 대조한다. 수집기·API 등록·준비 조회가 이 현재 핀을 다시 읽으므로 변경 전 증거를 현재 근거로 대신하지 않는다. 새 재관측/서명 인수는 §22의 기존 명령으로 진행한다.

발행자는 권한 있는 파일 검증 기록만 만든다. 설정 파일을 옮기는 것만으로 신뢰 전달이나 수신자 독립성이 완료되지 않는다. 별도 경로의 catalogId/전체 지문 전달·수신자 기준점/CAS·순차 설치/재시도·누락 버전 복구와 원격 공급자는 후속 작업이다. 이번 실제 PG 시험은 실제 dump/암호화/격리 복원 파일을 새 로컬 발행 CLI와 기존 API까지 연결한 합성 시험이며 외부 저장소·실회사 인수가 아니다. 실제 복원 PARTIAL, 최종4조건 UNVERIFIED, ready=false, ACCEPTANCE PASS 거부는 유지한다.

## 24. 별도 수신 폴더의 신뢰 지문·미수신 버전 따라잡기 (50차)

새 `tools/gw_checkpoint_transfer.py export/install`은 §23의 로컬 발행 폴더와 **별도 수신 폴더** 사이에서 보존된 서명 목록을 오프라인으로 전달한다. 전달 파일/목록 식별자/전체 지문은 담당자가 별도로 확인한다. 실제 네트워크 전송·다른 OS 사용자/장애 영역·외부 공급자 연결은 자동 설치하지 않았으며, 이번 합성 시험은 같은 OS 계정의 서로 다른0700 폴더다. 수신에 발행 개인키가 필요하지 않다. `admin` 로그인 이름은 파일 접근·서명 권한을 부여하지 않는다.

### 전달 기준점과 파일 계약

- 수신 담당자가 현재 `status`의 **revision/catalogDigest/pinDigest/catalogId**를 별도 기록과 대조한다. 상태 조회의 catalogDigest는 현재 목록 파일 지문, pinDigest는 수신자 경로를 포함한 현재 핀 파일 지문이다. 발행자와 수신자의 pinDigest는 일반적으로 다르며 서로 대신 사용하지 않는다. 최초 수신은 명시적인 빈 폴더/ABSENT만 허용한다.
- 발행 담당자는 수신자의 마지막 revision/catalogDigest를 `export --from-revision/--from-catalog-digest`에 넣는다. 최초는 `0/ABSENT`다. 도구는 발행 폴더의 건강한 현재 핀을 고정하고, 기준 버전부터 현재 버전까지 **모든 보존 스냅샷**을 읽어 서명·회사/세대·번호/시각·HEAD를 검증한다. 최초에는 버전1/기록번호1부터 필요하다. 수신자 기준점 자체도 전달 파일에 포함한다.
- 전달 문서는 v1 `CHECKPOINT_CATALOG_TRANSFER`이며 catalogId/workspaceId/generationId/baseRevision/baseDigest와 snapshots를 담는다. 각 snapshot은 version/revision/digest/content(원본 전체 바이트의 base64)다. 원래 개행/서명/파일 지문을 보존한다. 전달 묶음 자체는 새 운영 증거나 새 서명 종류가 아니다. **별도로 확인한 묶음 전체 SHA-256과 목록 식별자**, 각 원본의 현재 회사/CHECKPOINT_CATALOG 키 서명을 함께 검증한다. 업로드된 묶음에서 예상 지문을 자동 복사하지 않는다. 원문 보안 스냅샷·개인키·DB 접속 정보는 전달 파일에 넣지 않는다.
- 버전은 하나씩 증가해야 한다. 기록 번호가 같으면 결과/HEAD/시각/기준을 포함한 기록 전체가 같아야 한다. 새 기록은 번호+1/시각 비후퇴이며, FAIL/PARTIAL 뒤 PASS에는 실패 기록 이후 생성한 새 HEAD가 필요하다. 같은 생성 시각의 다른 HEAD·옛 생성 시각·같은 버전의 다른 파일을 허용하지 않는다. 중간 FAIL/PARTIAL·옛 기준도 보존하며 최신 옛 정책/코드/DB 기준을 현재 성공으로 꾸미지 않는다.
- 중간 스냅샷은 현재의15분 기한보다 오래돼도 역사 검증 대상으로 읽는다. 마지막 대상의 발행 시각은15분/미래30초를 검사한다. 모든 과거 원본도 **현재 신뢰 권한**으로 검증하므로 회수된 과거 키가 있으면 우회하지 않고 차단한다. v1 목록의 연속 번호/각 서명을 대조하는 방식이며, 원본 형식을 과거 해시로 연결한 새 서명 체인으로 변경하지 않는다.

```sh
# 발행 담당자. 수신자가 별도로 확인한 마지막 버전/목록 지문을 사용한다.
uv run --project backend python tools/gw_checkpoint_transfer.py export \
  --directory /private/gw-catalog --context /private/gw-input/context.json \
  --from-revision 0 --from-catalog-digest ABSENT \
  --output /private/gw-outgoing/transfer-new.json
# 담당자가 파일을 별도 전달하고, catalogId/transferDigest를 별도 신뢰 경로로 확인한다.
# 수신 담당자. 발행 개인키 환경은 필요하지 않다.
uv run --project backend python tools/gw_checkpoint_transfer.py install \
  --directory /private/gw-receiver --context /private/gw-input/context.json \
  --transfer /private/gw-incoming/transfer-new.json \
  --expected-transfer-digest "$GW_TRANSFER_DIGEST" --expected-catalog-id "$GW_CATALOG_ID" \
  --expected-pin-digest ABSENT --initialize
# 다음 전달은 수신 status의 revision/catalogDigest에서 export하고,
# install에는 수신자의 현재 pinDigest를 지정한다. --initialize는 다시 쓰지 않는다.
```

출력은 제한된 식별자/버전·기록번호/결과·지문과 `ready=false`다. export 종료0은 파일 생성 결과다. install은 파일 기록 PASS이면서 제공된 현재 문맥과 일치하고 대상이15분 기한 안일 때 종료0, 최신 FAIL/PARTIAL·옛 문맥 또는 만료된 보류 이력 완료는 종료2다. `contextMatches`와 `targetFresh`를 별도로 출력한다. 설치·원본 대조 오류는 종료1이다. 어떤 종료 코드도 ACCEPTANCE PASS/외부 인수/운영 전환 승인이 아니다. 기존 §22의 재관측·서명 수집/등록을 별도로 실행한다.

### 수신 차단·원자 교체·재시도

- 전용0700 폴더/0600 일반 파일·소유자/링크/크기·중복 JSON을 검사한다. 발행/수신 폴더를 혼용하지 않는다. 수신자 식별자 파일 `.catalog.receiver`가 회사/세대/목록 ID/최초 전달 지문을 보존한다. 발행 도구는 수신 폴더에서 발행/서명 복구하지 못하며, 수신 도구도 기존 발행 폴더를 바꾸지 않는다.
- 예상 수신 핀 CAS와 현재 회사/목록 식별자를 확인한 뒤, **전달 본문을 검증하기 전에** 확인된 예상 전달 지문/현재 기준점을 보류 기록에 fsync한다. 최신 전달 파일이 없거나 변조·서명 오류·이력 누락·다른 기준점·기한 초과이면 보류를 남겨 이전 성공 목록 읽기를 차단한다. 잘못된 예상 핀이나 기존 수신 폴더와 다른 회사/목록 입력은 현재 폴더를 변경하지 않는다. 예상 전달 지문 자체를 잘못 확인해 지정한 경우도 자동 변경/초기화하지 않으므로 담당자는 입력 전에 별도 기록을 대조해야 한다.
- 모든 버전 검증 후 각 원본 바이트를 새 비공개 임시 파일에 쓰고 fsync한 뒤 배타적 링크로 완성 파일만 게시한다. 보존된 같은 버전의 다른 바이트를 덮어쓰지 않는다. 링크 직후 중단으로 남은 **내용까지 동일한 자체 임시 별칭 하나**만 재시도에서 정리한다. 일반 하드링크/심볼릭 링크는 허용하지 않는다. 불완전 임시 파일과 기존 기록은 삭제·덮어쓰기하지 않는다. 현재 핀은 마지막에 한 번만 원자 교체/fsync하며 완료 후 보류를 제거한다.
- 보류 중에는 현재 핀이 이미 대상 버전으로 바뀌었더라도 읽기를 차단한다. `status`로 **실제 현재 pinDigest**를 확인하고, 같은 묶음/같은 예상 지문에만 `--resume`을 사용한다. 최초 중단으로 핀이 없으면 ABSENT다. 잘못 복사된 파일은 같은 기대 지문에 맞는 원본을 다시 받는다. 다른 묶음·이전 성공·초기화로 바꾸지 않는다. 보류/기준점 자체가 손상됐거나 확인한 원본 자체가 잘못됐다면 자동 복구하지 않고 조사한다.
- 보류 중 원래 묶음의15분 기한이 지났으면 `--resume`에 한해 **같은 지문의 유효한 원본**을 역사 검증으로 끝낼 수 있다. 미래 시각/서명·전체 버전 검증은 그대로이며 `targetFresh=false`/종료2다. 만료된 핀은 기존 읽기에서 계속 차단된다. 그 기준점부터 새로 발행한 신선한 묶음을 다시 받아야 현재 관측을 진행할 수 있다. 최초 설치/일반 갱신이나 완료된 묶음의 재사용에 이 예외를 적용하지 않는다.
- 완료 응답만 유실된 경우도 `--resume`은 같은 대상의 전체 바이트/모든 보존 버전을 재검증한다. 같은 버전의 다른 내용이나 후퇴를 완료된 재시도로 인정하지 않는다. 같은 예상 핀으로 동시 수신하면 하나만 진행한다. 발행자/수신자 OS 소유자의 악의적인 우회 쓰기를 차단하는 외부 CAS/WORM 증명이 아니다.

```sh
uv run --project backend python tools/gw_checkpoint_catalog.py status \
  --directory /private/gw-receiver --context /private/gw-input/context.json
uv run --project backend python tools/gw_checkpoint_transfer.py install \
  --directory /private/gw-receiver --context /private/gw-input/context.json \
  --transfer /private/gw-incoming/transfer-original.json \
  --expected-transfer-digest "$GW_TRANSFER_DIGEST" --expected-catalog-id "$GW_CATALOG_ID" \
  --expected-pin-digest "$GW_RECEIVER_CURRENT_PIN_DIGEST" --resume
```

운영자가 검토한 뒤 읽기 환경의 `FS_GW_CHECKPOINT_CATALOG_PIN_FILE`을 수신 폴더의 current-pin.json으로 지정할 수 있다. 도구는 서버 환경을 자동 교체/재시작하지 않는다. 기존 API·수집기·준비 조회가 수신 핀/보류를 다시 읽으므로 변경 전 관측이나 보류 중 이전 성공 상세를 대신 표시하지 않는다. 원격 발행과 수신/DB 등록 사이의 원자 거래·연속 감시는 아니다.

### 제한과 후속

1회는 **최대256개 스냅샷(기준 버전 포함)/8MiB**이며, 유실 없이 보존된 미수신 버전을 따라잡는 범위다. 초과 이력의 분할 전달은 아직 지원하지 않는다. **발행 중단으로 예약만 된 버전/기록 번호의 공백, 불완전·유실된 발행 원본은 건너뛰거나 추정하지 않고 차단한다.** §23의 PARTIAL 복구가 있어도 서명된 공백 복구 근거/이관 계약 없이 후퇴·공백을 허용하지 않는다. 손상/회수된 과거 키·확인한 전달 원본 자체 오류·수신 기준점 손상도 자동 리셋하지 않는다. 이 경우의 복구 명세/키 이관·분할/장기 용량 관리는 후속이다.

이번 검증은 실제 PG dump/암호화/폐쇄 복원 파일을 바탕으로 별도 로컬 수신 폴더→재관측v4/수집/API/준비 조회까지 연결한 합성 시험이다. 실제 외부 저장소/신뢰 전달 담당자·OS 계정/회사·기기/10인 인수는 아니다. 외부 독립성 false·실제 복원 PARTIAL·최종4조건 UNVERIFIED·ready=false·ACCEPTANCE PASS 거부를 유지한다.

## 25. 발행 중단 공백의 서명 복구 근거 (51차)

§23의 `recover-pending`은 이제 **서명 복구 근거를 포함한 목록 v2**를 만든다. §24의 수신자는 이 근거가 실제 직전 수신 기준점과 맞을 때만 공백 뒤의 새 PARTIAL을 연결한다. 공백을 성공 항목으로 채우거나 불완전 파일을 정상 목록으로 간주하지 않는다. 원래 v1 목록/서명 바이트·기존 API 인수 진단/RESTORE_RECHECK v4·정적/관리 핀 형식은 유지한다. 기존 v1만 처리하는 구형 읽기 환경은 v2를 사용할 수 없으므로 읽기/발행 도구를 함께 검토해야 한다. 실미리보기/운영 환경을 자동 변경하지 않는다.

### 복구 목록과 근거 계약

- 새 복구 목록은 기존 CHECKPOINT_CATALOG envelope의 `version=2`와 `recoveryProof`가 추가된 형식이다. 바깥 서명은 기존 `FS-GW-CHECKPOINT-CATALOG-v1` canonical/Ed25519 문맥을 유지하며 version과 proof 전체를 함께 서명한다. 일반 발행은 계속 v1이다. v2의 refresh는 최초 근거와 기록 전체를 그대로 유지하고 버전/발행 시각만 갱신한다.
- recoveryProof는 `{envelope,signature}`이며 별도 `FS-GW-CHECKPOINT-CATALOG-RECOVERY-v1` 문맥으로 현재 회사의 CHECKPOINT_CATALOG 권한 키가 서명한다. 발행/복구 키의 기존 단독 용도·회사 범위를 그대로 사용하며 `admin` 이름이나 인수 키로 대신하지 않는다. 새 DB 테이블·운영 증거 종류나 최종 인수 권한은 만들지 않는다.
- 근거 envelope v1은 kind=CHECKPOINT_CATALOG_RECOVERY, catalogId/workspaceId/generationId, baseRevision/baseDigest/baseSequence, targetRevision/targetSequence, recordDigest, recoveredAt, disposition=PARTIAL_HEAD_UNKNOWN, 원래 intent, slots, signerKeyId를 담는다. baseDigest는 **직전 정상적으로 읽힌 목록 전체 바이트** 지문이다. 최초로 핀이 없으면 baseRevision/baseSequence=0·baseDigest=ABSENT다. target은 예약/저장된 최고 번호 뒤의 새 기록이며 recordDigest는 새 PARTIAL 기록 전체 canonical SHA-256이다. 근거는 정책/코드/DB 기준과 기록 시각도 묶는다.
- intent는 중단 때 보존한 회사/세대/목록 ID·예약 버전/번호·예상 핀 지문이다. 원래 예약이 현재 핀 바로 다음이면 예상 핀도 실제 현재 값과 같아야 한다. 예약이 현재 기준보다 더 앞선 정상 발행이라고 꾸미거나 임의로 큰 예약 번호를 만들 수 없다. 핀이 이미 바뀐 뒤 중단됐거나 복구가 다시 중단된 경우에도 실제 현재 기준점과 예약 관계를 검사한다. 손상된 intent/현재 핀을 지우거나 추정해 복구하지 않는다.
- slots는 직전 기준 다음부터 새 복구 버전 직전까지의 모든 번호를 순서대로 담는다. 파일이 없으면 expectedDigest/actualDigest/size가 모두 null이다. 남아 있으면 이름에 있던 기대 지문·실제 전체 바이트 지문·실제 크기를 서명한다. **0바이트·잘린 JSON·아직 활성화하지 못한 완성 파일도 그대로** 보존하며 정상 서명 원본/성공으로 재분류하지 않는다. 당시 생성한 목록 메타데이터 파일 범위다. 다른 파일을 같은 이름으로 수동 배치하지 않는다.

새 목록의 기록은 반드시 PARTIAL/head=null이고 복구 시각·번호/기록 지문이 근거와 같아야 한다. 처음 발행한 v2의 발행 시각도 복구 시각과 같다. 바깥 목록만 다시 서명해 결과/정책/시각/HEAD를 바꾸거나 안쪽 근거의 회사/범위·서명·예약/구간을 바꾸면 거부한다. 같은 키의 서명이라도 서로 다른 문맥의 문서를 대체하지 못한다.

### 발행·전달·수신 순서

1. 발행 담당자는 §23의 status로 실제 핀/보류를 확인한 뒤 **기존 recover-pending 명령**을 실행한다. 개인키는 발행 환경에만 둔다. 별도 새 명령이나 수동 완료 체크는 없다. 과거 스냅샷/실패/불완전 원본을 덮어쓰거나 삭제하지 않는다.
2. 담당자는 §24의 기존 export 명령에 수신자의 마지막 revision/catalogDigest를 지정한다. 도구는 현재 목록에서 역으로 검증하면서, 서명 근거가 있는 복구 시점에서만 그 근거의 직전 기준으로 연결한다. 그 공백의 남은 원본과 실제 지문을 대조한다. 사라진 파일·달라진 바이트·없다고 서명한 뒤 나타난 파일은 차단한다. 근거 없는 일반 공백은 계속 거부한다.
3. 복구 근거가 포함되면 전달 묶음은 v2가 되고 `artifacts`가 추가된다. 각 artifact는 version=1/revision/digest(기존 이름의 기대 지문)/actualDigest/size/content(실제 바이트 base64)다. 일반 snapshots와 구별하며, 목록 원본 v2 안의 서명된 슬롯에 필요한 파일만 정확히 담는다. 근거 없는 추가/중복·누락/다른 바이트를 허용하지 않는다. 근거가 필요 없는 기존 v1 전달은 바이트 형식을 유지한다.
4. 수신 담당자는 기존 install 명령으로 별도 확인한 묶음 지문/목록 ID와 수신 핀을 지정한다. 각 서명/현재 키 권한과 실제 직전 수신 목록의 버전·번호·전체 지문이 근거의 base와 일치해야 한다. 수신 기준점이 공백 안에 있거나 다른 기준을 새 base라고 제시하면 차단한다. 아직 모르는 부분을 정상 원본으로 끼워 넣거나 v1으로 낮춰 공백을 숨기지 않는다.
5. 수신자는 불완전 원본까지 기존 이름/실제 바이트로 보존하되 현재 핀은 **새 복구 PARTIAL 목록만** 가리킨다. 기존 보류 선기록·완성 임시 파일/배타적 링크·최종 원자 핀 교체와 같은 원본 재시도 규칙을 유지한다. 0바이트 원본의 링크 직후 중단도 같은 바이트만 재시도하며 일반 목록 읽기가 빈 파일을 허용하는 것은 아니다.

복구/수신 도구의 성공 출력은 여전히 `ready=false`다. 새 복구와 전달된 최신 PARTIAL은 종료2이며, 기존 재관측의 목록 판정은 LATEST_PARTIAL/BLOCKED→ACCEPTANCE FAIL이다. 현재 목록이 달라지면 기존 등록 인수는 INVALID가 된다. 그 실패를 등록한 뒤에는 **실패 등록 이후 생성한 새 권한 대조·새 격리 복원·현재 재관측/인수 점검**이 필요하다. 같은 옛 HEAD를 새 번호로 발행하면 FAIL을 남긴다. 새 대조와 격리 복원 뒤의 후속 일부 확인도 이전 실패를 지우거나 최종 인수를 통과시키지 않는다.

### 범위와 남은 제한

복구 슬롯은 최대256개, 파일 하나는2MiB, 전달은 기존256스냅샷/256남은 원본·총8MiB 범위다. 초과 이력의 분할/장기 보관은 후속이며 초과 시 차단한다. **현재의 유효한 보류 intent와 읽을 수 있는 직전 핀**에 대한 복구다. 이미 보류를 잃은 과거 v1 복구, 기준점 자체의 손상, 복구 근거 없이 사라진 과거 발행 원본, 회수된 과거 서명 키를 자동 재구성/초기화하지 않는다. 잘못 확인한 수신 지문을 다른 묶음으로 바꾸는 기능도 없다.

서명은 허가된 발행자가 확인한 **중단/완료 불명 상태**의 근거다. 남은 완성 파일이 실제로 한 번도 공개되지 않았다는 물리 증명이나 공인 시각·발행자의 악의/누락·전체 이력 완전성·독립 담당자/장애 영역·WORM 증명이 아니다. 실제 외부 공급자/원격 전송은 계속 미정이며 같은 OS 계정의 합성 폴더 수신과 구분한다. 이번 실제PG 검사는 실제 dump/암호화/폐쇄 복원·고의 발행 중단/8바이트 원본 보존·서명 복구/수신·인수 무효화/실패 등록·새 대조/새 폐쇄 복원/후속 PARTIAL까지다. 전체CI/전체회귀·실회사/기기/10인 인수는 별도이며 실제 복원 PARTIAL·최종4조건 UNVERIFIED·ready=false·ACCEPTANCE PASS 거부를 유지한다.

## 26. 큰 목록 이력의 분할 전달·진행점 복구 (GW-READY-02 52차)

§24의 단일 묶음은 기존256개/8MiB 제한을 유지한다. 이보다 큰 이력에는 `tools/gw_checkpoint_segments.py`를 사용한다. **운영자가 별도 신뢰 경로로 확인한 manifest 전체 SHA-256과 catalogId**가 모든 조각·최종 목록 지문·실제 수신 기준점을 묶는다. manifest는 새 인수 증거/서명이 아니며 각 원본의 기존 회사별 서명과 현재 키 권한을 다시 검사한다. 발행 개인키는 수신자에게 주지 않는다. 공급자 미정 상태의 오프라인 파일 어댑터이며 원격 저장소/전송·서버 환경 설치를 자동화하지 않는다.

### 발행 담당자

현재 회사/세대/정책/버전의0600 context와 기존 공개키/용도 설정을 사용한다. 수신자 status의 마지막 **revision/catalogDigest**를 지정한다. pinDigest는 수신 CAS용이며 catalogDigest와 바꾸지 않는다. 최초 수신은0/ABSENT다. 패키지 폴더는 직접 만든 **빈0700 절대 폴더**이며 발행/수신 저장 폴더와 별개다.

```sh
uv run --project backend python tools/gw_checkpoint_segments.py export \
  --directory /operator/published \
  --context /operator/config/context.json \
  --from-revision 0 --from-catalog-digest ABSENT \
  --output-directory /operator/packages/new-session
```

원본 전체를 메모리에 합치지 않고, 최종 목록부터 역으로 검증해 `part-00001.bin`부터 각 원본의 **실제 바이트**를 새0600 파일에 보존한다. 서명 복구 구간의0바이트/잘린 원본도 조각으로 전달한다. 없는 슬롯은 서명 근거로만 확인하며 파일을 만들어 채우지 않는다. 마지막에만 manifest.json을 쓰고 지문을 출력한다. 중간에 실패한 출력 폴더의 파일을 완성 패키지로 쓰지 않고 새 빈 폴더에서 재실행한다. 중간 조각 지문을 새 최종 기준점으로 바꾸지 않는다.

manifest v1은 kind=CHECKPOINT_CATALOG_SEGMENTS, catalogId/회사·세대, baseRevision/baseDigest, targetRevision/targetDigest와 순서가 고정된 parts를 가진다. 각 part는 version=1/kind(SNAPSHOT 또는 ARTIFACT)/revision/digest(원래 이름의 지문)/actualDigest/size다. 일반 원본의 두 지문은 같고, 불완전 원본은 서명 복구 슬롯의 기대 지문·실제 지문/크기를 따로 보존한다. 중복/추가·형식 낮춤·범위/최종 지문 불일치를 거부한다.

### 수신 담당자

아래 값은 입력 파일에서 자동 추출해 신뢰하지 않는다. `CONFIRMED_MANIFEST_SHA256`·`CONFIRMED_CATALOG_ID`는 별도 확인값으로 바꾼다. 최초는 비어 있는0700 수신 폴더와 ABSENT/--initialize를 명시한다. 기존 수신은 실제 현재 핀 지문을 지정하고 --initialize를 생략한다.

```sh
uv run --project backend python tools/gw_checkpoint_segments.py receive \
  --directory /operator/received --context /operator/config/context.json \
  --manifest /operator/incoming/manifest.json \
  --expected-manifest-digest CONFIRMED_MANIFEST_SHA256 \
  --expected-catalog-id CONFIRMED_CATALOG_ID \
  --expected-pin-digest ABSENT --initialize
```

이 명령은 CAS/회사·기존 목록/수신 역할을 확인한 뒤 **본문을 해석·검증하기 전에 보류 상태를 저장**한다. 확인된 지문의 manifest가 누락/변조돼도 이전 성공을 운영 근거로 다시 사용하지 않는다. 정상 시작 출력은 state=RECEIVING/nextPart이며 종료2다. 이후 출력의 nextPart에 해당하는 원본을 같은 지문·현재 핀/--resume으로 전달한다. 이미 가진 정확한 기준 원본은 다시 전송하지 않아도 다음 번호 계산에 반영된다.

```sh
uv run --project backend python tools/gw_checkpoint_segments.py receive \
  --directory /operator/received --context /operator/config/context.json \
  --manifest /operator/incoming/manifest.json \
  --expected-manifest-digest CONFIRMED_MANIFEST_SHA256 \
  --expected-catalog-id CONFIRMED_CATALOG_ID \
  --expected-pin-digest CURRENT_RECEIVER_PIN_SHA256 --resume \
  --part-number 1 --part-file /operator/incoming/part-00001.bin
```

한 호출은 다음 조각 또는 이미 저장한 동일 조각의 재시도만 허용한다. 파일을 완성 임시 파일/fsync·배타적 링크로 보존하며 기존 바이트를 덮지 않는다. 중단 후 별도 숫자 진행 파일을 믿지 않고 현재 불변 파일의 이름/소유자/권한·형태/크기에서 진행점을 다시 구한다. **receivedParts는 저장 진행 수이며 전체 바이트/서명 검증 완료 수가 아니다.** 모든 원본의 실제 지문·서명/현재 권한·회사/세대·정확한 버전/번호/시각·실패 이후 새 HEAD·복구 근거/직전 기준/원본을 최종 단계에서 다시 읽어 검증한다. 저장 후 같은 크기로 변조된 파일도 최종 활성화 전에 차단한다.

같은 명세 지문/목록 ID/현재 핀을 지정해 `status`를 호출하면 다음 조각을 읽기 전용으로 확인한다. --initialize/--resume/--part-*는 status에 넣지 않는다. 중단 직후 현재 핀 지문은 §23의 status로 재확인한다. 핀 교체 직후 응답이 유실됐다면 이미 바뀐 실제 핀 지문을 사용한다. 중단된 완성 링크 정리가 필요한 상태는 receive --resume에서 처리하며 status가 파일을 정리하지 않는다.

```sh
uv run --project backend python tools/gw_checkpoint_segments.py status \
  --directory /operator/received --context /operator/config/context.json \
  --manifest /operator/incoming/manifest.json \
  --expected-manifest-digest CONFIRMED_MANIFEST_SHA256 \
  --expected-catalog-id CONFIRMED_CATALOG_ID \
  --expected-pin-digest CURRENT_RECEIVER_PIN_SHA256
```

마지막 조각 저장 뒤 전체 검증을 통과해야 **한 번만 최종 핀을 원자 교체**하고 보류를 끝낸다. 중간 수신은 현재 핀을 바꾸거나 보류를 해제하지 않으며 기존 API/수집기는 이전 성공도 읽지 못한다. 모든 파일은 왔지만 핀 교체 전 중단된 경우 status는 AWAITING_FINALIZE/sourceResult를 보여주고 성공 판정을 하지 않는다. 같은 receive --resume(조각 옵션 없이 가능)으로 최종화를 재시도한다. 완료 응답 유실은 같은 보존 manifest/실제 최종 지문만 재확인하며 다른 명세로 완료를 주장하지 못한다.

완료는 state=COMPLETE다. **최신 원본 PASS·현재 정책/코드/DB 기준 일치·15분 안 확인**이 모두 맞을 때만 CLI 종료0이며 나머지는2, 오류는1이다. 모든 출력은 ready=false다. PARTIAL/FAIL·옛 정책/버전을 이전 PASS로 대체하지 않는다. 보류 중 기한이 지난 같은 원본은 명시적 --resume으로 이력 보존만 마칠 수 있고 targetFresh=false/종료2이며 현재 읽기는 계속 STALE로 막힌다. 새 확인 목록을 별도 후속 세션으로 받아야 한다. 미래30초 초과는 재시도에서도 거부한다. 잘못 확인한 명세/손상 기준점/근거 없는 유실·회수된 과거 키를 자동 초기화하거나 다른 지문으로 교체하지 않는다.

### 한계와 인수 경계

조각 하나2MiB·최대8192원본, manifest2MiB의 먼저 도달하는 제한을 적용한다. 일반 수신 읽기는 빈 파일/임의 하드링크를 허용하지 않는다. 기존 복구 서명은 최대256슬롯 제한을 유지한다. 총8192개/최대 용량에서의 성능·장기 보관/공급자 장애 복구는 검증하지 않았다. 수신마다 메타데이터를 점검하고 최종에 전체 원본을 다시 읽으므로 큰 이력에서는 시간/디스크 여유가 필요하다.

최종화 후에도 최초 명세와 원본/이전 실패를 보존한다. 단일 묶음과 분할 세션의 보류 상태는 서로 바꿔 재시도하지 않는다. 서명 키를 현재 권한에서 제거하면 과거 원본 검증도 막히며 과거 키 이관은 후속이다. 이 전달은 외부 독립 보관·사람/장애 영역 독립·전체 무누락·실회사10인/운영 전환 인수가 아니다. 실제 복원은 PARTIAL/최종4조건 UNVERIFIED/ready=false·ACCEPTANCE PASS 거부를 유지한다.

## 27. 목록 서명 키의 정상 교체와 침해·회수 구분 (GW-READY-02 53차)

이 절은 **CHECKPOINT_CATALOG 발행 키의 최초 정상 교체 한 단계**를 다룬다. BACKUP/RESTORE/CHECKPOINT_HEAD·재관측/인수 키의 권한을 확장하지 않는다. 정상 교체는 교체 전에 대조한 **정확한 목록 원본·복구 서명 근거**만 과거 검증용으로 남긴다. 현재 목록의 바깥 서명과 새 발행/이관은 계속 활성 키를 요구한다. **침해·권한 회수(REVOKED)는 과거 이관 근거가 있어도 거부**한다. 로그인 이름 admin과 이 권한은 관계가 없다.

이관 자료는 새 인수 증거나 운영 전환 체크가 아니다. CLI가 서버 신뢰 설정/운영 환경을 설치하거나 키를 생성·삭제/배포하지 않는다. 운영 담당자가 정상 교체인지 침해·회수인지 먼저 판단해야 하며, 자료의 이중 서명은 무침해·공인 시각·개인키 삭제의 물리 증명이 아니다.

### 정상 교체 순서

1. 기존 키와 별개의 새 키를 같은 회사의 CHECKPOINT_CATALOG 단독 용도로 등록한다. 기존 공개키/허용 회사·용도 설정과 새 키가 모두 아직 활성인 동안 진행한다. 다른 키 ID에 같은 공개키를 넣거나 기존 ID의 공개키를 바꾸지 않는다. 발행자는 기존 `FS_GW_CATALOG_KEY_FILE/ID`와 별도의 `FS_GW_CATALOG_SUCCESSOR_KEY_FILE/ID`를 비공개 환경에서 사용한다. 개인키 파일은 기존과 같은32바이트/0600·0700 부모이며 값을 로그/채팅에 넣지 않는다.
2. 기존 키의 발행을 멈추고 §23 status로 실제 현재 핀을 확인한다. 현재 목록은 정상 보존/보류 없음·15분 이내여야 한다. 현재 시각이 발행 시각보다 앞서거나 과거 원본/복구 근거가 없거나 변조됐다면 차단한다. 다음 명령은 원본/핀을 변경하지 않고, 현재 회사·세대의 전체 보존 구간을 다시 대조해 별도0600 이관 파일을 만든다.

```sh
uv run --project backend python tools/gw_catalog_key_handover.py issue \
  --directory /operator/published --context /operator/config/context.json \
  --retiring-key-id CURRENT_CATALOG_KEY_ID \
  --expected-pin-digest CONFIRMED_CURRENT_PIN_SHA256 \
  --output /operator/handovers/normal-retirement.json
```

3. 출력의 handoverDigest와 기존/새 키·회사/세대/목록 ID, capturedRevision을 별도 경로로 확인한다. 원본은 덮어쓰지 않는다. 이관 직후 기존 키로 새 목록이 추가됐다면 그 파일은 허용 목록에 없으므로 차단되며, **기존 키가 아직 활성일 때** 현재 원본을 다시 확인해 새 이관 자료를 발급해야 한다. 이관 파일의 번호/시각만 편집하거나 옛 키로 뒤늦게 소급 서명하지 않는다.
4. 아직 두 키가 모두 활성인 동안 발행 환경의 현재 발행 키를 새 키로 바꾸고 기존 §23 **refresh**로 새 바깥 서명의 다음 버전을 발행한다. 이전 기록/번호/결과·복구 근거는 바꾸지 않는다. 기존 최신 FAIL/PARTIAL도 그대로다. 기존 키를 먼저 RETIRED로 지정하면 현재 옛 목록 읽기/발행은 차단되므로 도구가 그 순서를 자동 우회하지 않는다.
5. 운영 담당자는 기존 공개키를 활성 공개키/용도 목록에서 제외하고, 아래와 같은 **서버/도구 소유 `FS_GW_CATALOG_KEY_LIFECYCLE` JSON**에 원래 키 ID·공개키·회사·상태와 별도 확인한 이관 파일/전체 지문을 설정한다. 소스와 수신 환경의 고정 경로는 각 환경의 실제0700/0600 파일 경로여야 한다. 업로드나 선택한 HEAD/전달 명세에서 이 설정/키를 자동 가져오지 않는다. 아래 값은 형식 설명용이며 실제 확인값으로 바꾼다.

```json
{
  "version": 1,
  "keys": [{
    "version": 1,
    "workspaceId": "10",
    "keyId": "previous-catalog",
    "publicKey": "BASE64_OF_CONFIRMED_PREVIOUS_PUBLIC_KEY",
    "state": "RETIRED",
    "approvals": [{
      "version": 1,
      "file": "/operator/handovers/normal-retirement.json",
      "digest": "CONFIRMED_HANDOVER_SHA256"
    }]
  }]
}
```

기존 키가 실수로 활성 목록에 남아 있어도 RETIRED/REVOKED 현재 서명 권한은 거부한다. 키 ID/공개키 재사용·별칭, 다른 회사의 허용, 미확인/중복 승인·잘못된 경로/권한/지문/서명/형식은 차단한다. 이관 자료의 새 키는 **지금도 해당 회사의 활성 단독 발행 권한**이 있어야 한다. 그 새 키가 제거/회수/다시 은퇴했다면 기존 자료만으로 승인을 연쇄 추론하지 않는다.

6. 개인키 없이 아래 inspect로 현재 설정을 확인한다. RETIRED의 approvedDocuments는 정확한 과거 목록/복구 근거 개수이며 운영 인수 통과 수가 아니다. 정상 조회도 종료2/ready=false다. 오류는1, issue의 자료 생성 성공은0이며 어느 명령도 운영 완료를 뜻하지 않는다.

```sh
uv run --project backend python tools/gw_catalog_key_handover.py inspect \
  --context /operator/config/context.json --retiring-key-id previous-catalog
```

7. §24/§26의 기존 전달을 실행한다. 수신자가 아직 옛 키의 현재 핀을 가지고 있으면 운영 읽기는 차단된다. 수신 도구만 실제 CAS/기준점과 일치하는 승인된 옛 바이트를 **이전 기준점/중간 이력으로** 검증해 다음 활성 키의 최종 목록까지 연결할 수 있다. 옛 키의 정확한 승인 파일이라도 최종 현재 목록으로 활성화할 수 없다. 단일/분할 수신의 보류 선기록·전체 재검증·최종 핀 교체/재시도 규칙은 유지한다. 수신자에게 기존/새 개인키를 전달하지 않는다.

### 이관 계약과 복구 근거

`CHECKPOINT_CATALOG_KEY_HANDOVER` v1은 handoverId/목록 ID·회사/세대, NORMAL_RETIREMENT/issuedAt, 기존·새 키 ID/공개키 전체 SHA-256, 현재 캡처 버전/전체 원본 지문·기록번호/기록 전체 지문, 기존 키가 서명한 정확한 snapshots(revision/digest), recoveryProofs(기존 복구 문서 전체의 canonical 지문)를 묶는다. 서명 문맥은 `FS-GW-CATALOG-KEY-HANDOVER-v1`과0바이트이며, 기존/새 역할마다 `RETIRING`/`SUCCESSOR`와0바이트를 앞에 붙여 역할별로 서명한다. 두 서명·회사/키 지문/현재 새 키 권한을 모두 대조한다. 목록 바깥 서명·복구 서명의 기존 문맥/원본 바이트는 바꾸지 않는다.

과거 허용은 **회사·세대·목록 ID·원본 전체 지문·목록 버전**과 일치해야 한다. 캡처 원본의 실제 기록번호/기록 전체 지문도 이관 메타데이터와 대조한다. 두 키로 다시 서명한 자료라도 이 값이 실제 원본과 다르면 거부한다. 허용 시각은 이관 발급 시각을 넘지 않아야 하지만 **시각만으로** 원본을 허용하지 않는다. 옛 개인키를 가진 사람이 나중에 만든 새 버전/같은 버전 분기·소급 날짜/다른 회사/세대·목록·추가 원본은 정확한 지문 목록에 없으므로 차단한다.

현재 새 키가 서명한 목록 안에 기존 PARTIAL 복구 근거가 그대로 남아 있다면, 그 **안쪽 문서의 정확한 지문**만 별도의 과거 검증으로 허용한다. 복구 원본/기준점 대조·PARTIAL/head=null 계약은 그대로다. 바깥 활성 서명이 새로 있어도 안쪽 근거를 변조하거나 그 키가 REVOKED가 되면 거부한다. 불완전 원본을 성공 목록으로 바꾸거나 과거 실패를 삭제하지 않는다.

### 침해·회수와 오류 처리

침해/회수 시 해당 키의 현재 상태는 **REVOKED**, approvals는 **빈 배열**이어야 한다. 이전 이관 파일을 삭제·수정해 정상 은퇴처럼 꾸미지 않는다. REVOKED에 승인 파일을 남긴 모순된 설정도 거부한다. 현재 설정이 REVOKED이면 과거 이중 서명·원본 지문 일치·아직 남은 활성 공개키와 관계없이 그 키의 목록/복구 검증을 거부한다. 원래 키를 없애거나 침해한 뒤 정상 이관 자료를 소급 발급할 수 없다. 이관 설정이 없고 옛 활성 키도 없으면 기존과 동일하게 거부하며 자동 은퇴로 추정하지 않는다.

각 명령/API 요청은 현재 서버 신뢰 설정과 고정 지문의 이관 파일을 다시 읽는다. 파일 누락/권한/서명/중복 JSON·깊이/형식 오류는 안전한 구성 오류로 처리하며 운영 화면은 CONFIG_REQUIRED/ready=false가 된다. 현재 목록 서명/안쪽 근거가 회수돼 대조에 실패하면 INVALID 또는 점검 차단으로 남긴다. 과거 성공을 대신 표시하지 않는다. 파일 손상은 동일한 고정 지문의 원본으로 복구·재시도하며 다른 자료로 자동 초기화하지 않는다. 실제 인수 실패를 등록했다면 기존의 **실패 이후 새 권한 대조·새 폐쇄 복원/현재 점검** 규칙을 유지한다.

### 범위와 남은 검증

- 이번 범위는 목록 키의 **현재 활성 새 키가 직접 확인하는 한 단계 정상 교체**다. 새 키까지 다시 교체할 때의 이관 연결·더 오래된 키의 개인키 없이 재승인하는 계약은 후속이다. 현재는 승인자의 권한을 재확인할 수 없으면 차단하며 여러 단계/순환 위임을 자동 허용하지 않는다.
- 수명 상태 설정은64KiB/100회사-키 항목, 승인 파일은 전체20개/각2MiB, 파일당8192목록/8192복구 지문과 기존 전체 이력8192원본 제한을 적용한다. 먼저 도달한 제한에서 차단하며 최대 용량/장기 성능은 미검증이다.
- 서버 신뢰 설정은 운영자 소유 입력이다. 설정 자체의 악의적 롤백·실수로 회수 상태를 정상 은퇴로 덮는 것을 막는 독립 영구 회수 원장/WORM은 아직 없다. **REVOKED를 RETIRED로 되돌리는 복구 절차는 제공하지 않는다.** 현재 회수 우선 검증과 설정 자체의 물리적 롤백 방지는 서로 다르다.
- 단일 호출은 로드한 신뢰 스냅샷을 사용하며 다음 명령/API 요청에서 다시 읽는다. 서명은 허가된 두 발행 키의 진술이고 독립 담당자/시간·개인키 삭제/장애 영역·전체 무누락을 증명하지 않는다. 실제 외부 공급자/운영 환경 설정·실계정/개인키 삭제를 이번 작업에서 변경하지 않았다.
- 실제 복원 PARTIAL·최종4조건 UNVERIFIED·ready=false/ACCEPTANCE PASS 거부는 유지한다. 전체CI/전체회귀·실외부/실회사·기기/10인/최종전환·최신main 통합/원격push/배포는 별도다.

## 28. 여러 차례 목록 키 교체의 이관 연결 (GW-READY-02 54차)

§27의 한 단계 A→B를 마친 뒤 B→C로 다시 교체할 때 **A의 개인키 없이** A의 정확한 과거 승인을 연결한다. A의 원래 이관 파일과 허용 원본/복구 지문·허용 시각은 그대로 보존한다. B와 C는 그 파일 전체 지문과 현재 B의 별도 이관 자료를 역할별로 서명한다. 이름/날짜만 바꾸거나 은퇴 키 전체를 다시 활성 키로 간주하지 않는다. 현재 바깥 목록 서명은 계속 활성 최종 키가 필요하다.

### B→C 교체 순서

1. A는 RETIRED/기존 승인 파일·공개키/회사 설정을 유지하고 B는 현재 활성 상태로 둔다. C를 같은 회사의 별개 CHECKPOINT_CATALOG 단독 활성 키로 준비한다. B의 `FS_GW_CATALOG_KEY_FILE/ID`, C의 `FS_GW_CATALOG_SUCCESSOR_KEY_FILE/ID`만 발급 환경에 필요하다. A의 개인키 파일/환경을 읽지 않는다. 이 도구가 실환경 키를 생성·삭제/배포하거나 서버 설정을 설치하지는 않는다.
2. B의 발행을 잠시 멈추고 §23 status로 실제 핀을 확인한다. §27의 **issue** 명령을 B/C로 실행해 B→C 원래 이관 파일을 만든다. 전체 보존 이력/복구 구간을 현재 권한으로 대조하며 A는 기존에 승인한 정확한 과거 원본으로만 검증한다. 새 파일의 전체 지문을 별도 확인한다.
3. 더 오래된 각 은퇴 키의 **현재 설정에 고정한 승인 파일**을 부모로 지정해 아래 extend를 실행한다. 첫 반복에서는 A 하나다. 이후 C→D 교체에서는 A/B 각각의 현재 승인 파일을 별도로 연결해야 한다. 같은 회사 안에서도 목록/세대가 다르면 해당 context와 각각의 승인 자료가 필요하다. 모든 연결 자료는 같은 현재 발행 핀/실제 캡처에 맞아야 하며, 중간에 발행이 진행됐으면 이전 캡처를 새 현재 자료인 것처럼 쓰지 않는다.

```sh
uv run --project backend python tools/gw_catalog_key_handover.py extend \
  --directory /operator/published --context /operator/config/context.json \
  --retiring-key-id catalog-b --expected-pin-digest CONFIRMED_B_PIN_SHA256 \
  --predecessor-key-id catalog-a \
  --parent-file /operator/handovers/current-a-approval.json \
  --expected-parent-digest CONFIRMED_CURRENT_A_APPROVAL_SHA256 \
  --retiring-handover-file /operator/handovers/b-to-c.json \
  --expected-retiring-handover-digest CONFIRMED_B_TO_C_SHA256 \
  --output /operator/handovers/continued-a-to-c.json
```

부모는 입력자가 새로 고른 임의 지문이 아니라 **현재 서버 신뢰 스냅샷에 고정된 해당 은퇴 키 승인 지문**이어야 한다. 같은 의미의 JSON이라도 다른 바이트/지문은 새 부모로 추정하지 않는다. B→C 자료는 두 활성 키의 서명뿐 아니라 실제 현재 B 목록의 ID/회사·세대·전체 지문/버전·기록번호/기록 지문·확인 시각과 맞아야 한다. 해당 키가 서명한 저장 원본/복구 지문 목록도 현재 보존 이력과 **정확히 같아야** 하며 누락/추가·소급 발급은 거부한다. 잘못된 CAS·부모/자기 이관/원본·권한/시계·서명이면 새 연결/현재 핀을 발행하지 않는다.

4. 출력의 handoverDigest/rootHandoverId/capturedRevision/edges를 확인한다. edges는 최초 이관을 포함한 연결 수이며 인수 통과 수가 아니다. 자료 생성 성공은 종료0/ready=false다. 승인자 자신의 B→C 원래 이관과 더 오래된 각 키의 연결 자료를 모두 준비한 뒤, 아직 B/C가 활성인 동안 C의 기존 refresh로 다음 목록을 발행한다. 실패/일부 기록과 안쪽 복구 근거는 그대로 둔다.
5. 활성 공개키/목적 목록에서 B를 제외하고 §27과 같은 `FS_GW_CATALOG_KEY_LIFECYCLE` v1 설정에 B의 **원래 B→C 파일**을 RETIRED 승인으로 추가한다. A의 원래 공개키/회사·RETIRED 상태는 바꾸지 않고 승인 파일/핀만 새 A→C 연결 자료로 지정한다. C는 활성 키/회사·단독 목적 설정에 남기며 은퇴/회수 항목으로 지정하지 않는다. 기존 원본·이전 이관 파일은 덮거나 지우지 않는다. 예시 구조의 지문/공개키/경로는 실제 별도 확인값으로 바꾼다.

```json
{
  "version": 1,
  "keys": [
    {"version": 1, "workspaceId": "10", "keyId": "catalog-a",
     "publicKey": "CONFIRMED_A_PUBLIC_KEY_BASE64", "state": "RETIRED",
     "approvals": [{"version": 1, "file": "/operator/handovers/continued-a-to-c.json", "digest": "CONFIRMED_A_CONTINUATION_SHA256"}]},
    {"version": 1, "workspaceId": "10", "keyId": "catalog-b",
     "publicKey": "CONFIRMED_B_PUBLIC_KEY_BASE64", "state": "RETIRED",
     "approvals": [{"version": 1, "file": "/operator/handovers/b-to-c.json", "digest": "CONFIRMED_B_TO_C_SHA256"}]}
  ]
}
```

6. 기존 공개키만 필요한 inspect로 전체 설정의 현재 연결/권한을 확인한다. approvedDocuments는 **원래 허용한 목록/복구 문서 수**이며 새 연결 수나 운영 준비 통과 수가 아니다. 같은 회사의 승인 파일 하나라도 잘못됐거나 중간 키의 현재 상태/원래 이관을 확인하지 못하면 안전한 구성 오류로 차단한다. 과거 성공/낮은 단계의 승인 파일을 대신 선택하지 않는다.
7. §24/§26의 단일/분할 전달을 기존처럼 진행한다. 옛 현재 핀은 일반 운영 읽기에 사용할 수 없고, 수신 도구만 정확한 옛 기준점/중간 이력으로 대조해 활성 C의 최종 목록까지 연결할 수 있다. 수신자에게 A/B/C 개인키를 전달하지 않는다. 전체 바이트/현재 승인·회수 상태 재검증·보류/원자 핀 교체 규칙은 유지한다. 실제 인수 미통과를 등록했다면 실패 이후 새 권한 대조·새 폐쇄 복원/현재 점검이 계속 필요하다.

### 연결 문서의 검증 계약

`CHECKPOINT_CATALOG_KEY_CONTINUATION` v1은 continuationId/rootHandoverId·회사/세대/목록, NORMAL_RETIREMENT_CONTINUATION, 기존 부모의 전체 지문과 **원래 바이트의 base64**, 현재 은퇴하는 키의 원래 이관 파일 전체 지문(retiringHandoverDigest), 현재/다음 키 ID·공개키 지문·시각과 실제 캡처 버전/목록 지문·번호/기록 지문을 묶는다. 새 서명 문맥은 `FS-GW-CATALOG-KEY-CONTINUATION-v1`+0바이트이며 역할별 RETIRING/SUCCESSOR+0바이트를 앞에 붙인다. 원래 이관/목록/복구 서명 문맥과 바이트는 바꾸지 않는다.

검증은 중첩 부모의 실제 지문과 모든 역할 서명, 같은 회사/세대/목록과 최초 이관 ID, 앞 단계의 다음 키와 뒷 단계의 현재 키/공개키, 증가하는 실제 캡처 버전·후퇴하지 않는 번호/시각을 대조한다. 같은 번호의 기록 지문은 같아야 한다. 키 ID/공개키·연결 ID/최초 이관 ID의 반복과 순환·잘못된 부모/형식 낮춤은 거부한다. **과거 허용 원본과 허용 시각은 최초 이관의 값이며 뒤의 연결 시각으로 넓히지 않는다.**

모든 중간 키의 공개키와 RETIRED 상태는 **현재 운영자 소유 설정**에 있어야 한다. 연결 문서 안에서 신뢰 키/권한을 가져오지 않는다. 각 중간 키는 같은 범위의 자기 원래 이관도 현재 승인 파일로 보존해야 하며, 해당 원래 문서의 전체 지문/직접 다음 키·캡처 값이 연결 문서와 정확히 같아야 한다. A→B→C와 B→C를 서로 대조한다. B→C→D로 이어질 때도 B의 원래 B→C 바이트는 안쪽에 남고 C의 원래 C→D와 새 연결을 함께 대조한다. 범위별 원래 이관/캡처가 중복/분기하거나 자기 자료가 없으면 거부한다.

마지막 키는 **지금도 활성인 해당 회사의 CHECKPOINT_CATALOG 단독 권한**이어야 한다. 옛 A→B 자료를 재생해 은퇴한 B를 마지막 승인자로 사용할 수 없다. 원래 키/중간 키/최종 키의 현재 회수·누락·허용 회사/용도 상실은 모두 차단한다. 유효한 새 바깥 서명도 회수된 안쪽 복구 근거나 연결을 부활시키지 않는다. 오류는 CONFIG_REQUIRED/INVALID·보류/ready=false로 남고 이전 성공을 대신하지 않는다.

### 범위와 남은 제약

- 최초 이관 포함 **최대8연결**, 파일 하나2MiB/부모를 풀어 읽은 누적8MiB, 기존 설정64KiB/100회사-키·승인 전체20파일/각2MiB·원본/복구 지문 한도 중 먼저 도달하는 제한을 적용한다. 한도 초과는 새 연결/현재 핀 변경 없이 거부한다. 최대8연결을 넘는 압축·새 신뢰 기준점 전환은 지원하지 않는다. 최대 파일 용량/장기 성능 검증은 별도다.
- 새 승인 파일을 읽으려면 54차 검증기가 필요하다. 이전 한 단계 전용 검증기는 새 형식을 거부하며 운영 환경/바이너리를 도구가 자동 업데이트하지 않는다. 한 단계 자료와 설정 v1·목록/복구/전달 형식은 유지한다.
- 현재 설정 아래에서 회수·재생을 거부하는 검증이다. **독립 영구 회수 원장/서버 신뢰 설정 자체의 악의적 롤백 방지**는 아직 없으며, REVOKED를 RETIRED로 되돌리는 복구 도구/절차를 제공하지 않는다. 여러 서명도 무침해·개인키 실제 삭제·공인 시각/독립 담당자·장애 영역/WORM/전체 무누락을 증명하지 않는다.
- 실제 외부 공급자/운영 환경·실계정/브라우저·실환경 키 삭제는 이번 범위가 아니다. 실제 복원 PARTIAL/최종4조건 UNVERIFIED·ready=false/ACCEPTANCE PASS 거부를 유지한다. 전체CI/전체회귀·최신main·실회사10인/최종전환·원격push/배포는 남아 있다.

## 29. 목록 신뢰 상태의 로컬 영구 이력·설정 후퇴 차단 (GW-READY-02 55차)

§27–28의 서명 검증에 **운영자 소유 보존 이력**을 더한다. `CATALOG_TRUST_FLOOR` v1은 원장 UUID·연속 revision·직전 파일 전체 지문과 회사별 목록 키 ID/공개키 지문·ACTIVE/RETIRED/REVOKED·승인 파일의 최초 원본부터 현재 연결까지의 지문 경로를 보존한다. 시간에 의한 인수 승인/새 인수 증거가 아니며 GW 업무 DB 스키마도 추가하지 않는다.

### 최초 설치와 정상 변경

- `FS_GW_CATALOG_TRUST_DIRECTORY`에 발행 원본/수신 패키지·임시 작업과 분리한 **절대 경로의 운영자 소유0700 보존 폴더**를 지정한다. 모든 기록/현재 기준점은0600·일반 파일·소유자/단일 링크를 요구한다. 이 환경 항목/서비스 실행 계정·경로와 폴더 전체의 보존 권한은 배포 담당자가 보호한다. 도구는 폴더를 자동 생성하거나 서버 환경을 설치/재시작하지 않는다. 실제 환경에는 이번 작업에서 설치하지 않았다.
- 목록 단독 권한이 있는 키 또는 수명 상태를 로드하는 서버/API/기존 CLI는 보존 경로와 현재 이력이 필수다. 경로 항목 제거·비어 있는 폴더·미설치·이력 오류·설정 불일치는 `CONFIG_REQUIRED`/명령 차단·ready=false다. 과거 설정의 활성 키를 다시 넣고 수명 상태 항목 전체를 지워도 기존 보존 상태와 맞지 않으면 차단한다. 목록 권한이 없는 환경에 목록 검증 권한을 새로 부여하지 않는다.
- 기존 환경은 자동 승격하지 않는다. 배포 전 담당자가 현재 키/회사·용도와 §27–28의 모든 원래 승인/회수 상태를 별도로 확인하고 **새 빈 폴더에 최초 한 번** 아래 initialize를 실행한다. 최초 설치 전 잃어버린 과거 회수 상태를 재구성한다는 뜻은 아니다. 이미 사용한 폴더를 비워 다시 초기화하거나 다른 새 경로로 옮겨 회수를 우회하지 않는다.

```sh
# FS_GW_EVIDENCE_PUBLIC_KEYS/KEY_SCOPES·기존 수명 상태와 보존 경로는 담당자가 비공개 주입한다.
uv run --project backend python tools/gw_catalog_trust.py initialize --expected-digest ABSENT
uv run --project backend python tools/gw_catalog_trust.py status
# 정상 변경을 제안한 환경에서 전체 서명/현재 권한 검증 후 직전 보존 지문과 대조한다.
uv run --project backend python tools/gw_catalog_trust.py advance --expected-digest CONFIRMED_CURRENT_TRUST_SHA256
```

`status`는 revision/digest/revokedKeys/ready=false만 반환하며 종료2다. initialize/advance/revoke/resume의 종료0은 로컬 기록 완료이며 운영 인수 통과가 아니다. 오류는 비공개 경로/키/설정/예외 전체를 출력하지 않고 종료1이다. 모든 변경은 배타적 잠금과 현재 전체 지문 CAS를 요구한다. 두 담당자가 같은 지문으로 다른 변경을 동시에 적용하면 한 명만 진행할 수 있다.

정상 교체는 **새 활성 키 추가 → advance → 기존 issue/extend·새 키 refresh → 은퇴/정확한 새 승인 연결 설정 → advance** 순서로 진행한다. 제안 설정을 바꾼 뒤 보존 이력에 설치하기 전에는 기존 API/도구가 잠시 구성 오류로 차단되는 것이 정상이다. 발행을 멈춘 유지보수 시간에 진행한다. 기존 RETIRED의 각 승인 경로는 원래 전체 지문 경로의 정확한 연장만 허용한다. 옛 승인 재생/같은 최초 문서의 다른 분기·최초 원본 변경·승인 추가/제거·은퇴 키 재활성화·ID/공개키 재사용·다른 ID/용도로의 전용을 거부한다. 활성 권한 삭제도 같은 회사의 명시적 RETIRED/REVOKED 기록이 필요하다. 다른 회사의 기존 상태도 함께 보존한다.

### 침해·회수는 먼저 보존한다

```sh
uv run --project backend python tools/gw_catalog_trust.py revoke \
  --workspace-id 10 --key-id catalog-b \
  --expected-digest CONFIRMED_CURRENT_TRUST_SHA256
```

이 명령은 **이미 보존한 키의 회사/공개키 지문**을 사용한다. 개인키나 정상인 현재 이관 연결이 필요 없으므로 중간 키 회수로 다른 연결이 깨지는 경우도 먼저 기록할 수 있다. 같은 상태의 명시 재요청은 새 기록을 늘리지 않는다. 그다음 서버 수명 상태를 같은 공개키/회사·REVOKED/approvals=[]로 맞춘다. 설정을 고치기 전의 과거 유효한 설정도 즉시 보존 기준과 달라 차단된다. 회수로 옛 연결이 유효하지 않으면 설정을 맞춘 뒤에도 계속 차단하며 과거 성공/옛 승인으로 복원하지 않는다. REVOKED→RETIRED/ACTIVE 전환이나 회수 원장 삭제/리셋 명령은 없다.

서버 조회가 임의 설정을 자동 승인/이력에 기록하지는 않는다. **환경만 REVOKED로 고치고 위 영구 기록을 생략하면 절차가 끝난 것이 아니다.** 목록 신뢰 설치/회수는 이 명시 도구와 보존 권한을 맡은 담당자의 작업이다. `admin`이라는 로그인 이름은 이 도구/OS 경로·회사 보안/서명 권한을 대신하지 않는다. BACKUP/RESTORE/HEAD·인수 키의 별도 권한과 실제 업무 계정은 확장하지 않는다.

### 중단과 보존 경계

새 기록은 배타적 새 파일 생성·파일/폴더 fsync로 보존한 뒤, `.trust-head.pending`을 보존하고 현재 기준점을 원자 교체·폴더 fsync한다. 조회는 **모든 원본의 실제 전체 지문/연속 번호·원장 ID·직전 연결·단조 상태 전이와 현재 기준점**을 다시 대조한다. 중간/최신 원본 삭제, 현재 기준점만 과거로 복원, 잘린 파일/바이트 변조·예상 밖 파일/권한·링크 오류/미완료 기준점은 과거 성공으로 대신하지 않는다. 호출은 로드한 신뢰 스냅샷을 사용하며 다음 명령/API 요청에서 다시 읽는다.

완성 새 기록이 남고 기준점 교체만 중단된 경우, 담당자가 **완성 기록 전체 지문을 별도로 확인한 뒤** 아래 명령으로 정확히 같은 한 단계만 마친다. 이 명령은 현재 환경/개인키에 의존하지 않아 회수 기록의 중단도 마칠 수 있다. 최초 기록이면 이전 기준점 없음, 이후이면 정확한 직전 기준점 또는 이미 동일한 완료 기준점만 허용한다.

```sh
uv run --project backend python tools/gw_catalog_trust.py resume --expected-digest CONFIRMED_COMPLETE_NEW_RECORD_SHA256
```

잘린 기록/보류 기준점·없는 원본·바뀐 직전 기준점은 resume으로 재생성/삭제하지 않는다. 실패 원본을 보존하고 별도로 보존한 **정확한 같은 원본** 복구가 필요하며 독립 외부 복구 경로는 후속이다. 해시 파일명에서 지문을 자동 선택하거나 오래된 폴더/기준점으로 초기화하지 않는다.

최대4096개 기록·기록 하나256KiB·최대2100회사-키 상태와 기존 설정/승인 한도 중 먼저 도달한 제한에서 차단한다. 최대 용량/장기 성능·압축/새 원장 전환은 미검증이다. **같은 OS 계정의 로컬 보존 어댑터**이므로 운영자가 경로를 다른 새 원장으로 바꾸거나 원본/현재 기준점·환경을 모두 과거로 되돌리는 공격, 호스트/모든 복제본 유실을 독립적으로 탐지하지 못한다. 별도 계정/장애 영역·외부 최신 지문 고정·WORM/공인 시각·전체 무누락 증명은 공급자 선정 후 검증해야 한다. 로컬 후퇴 차단을 독립 영구 원장 인수로 표현하지 않는다.

실제 복원 PARTIAL·최종4조건 UNVERIFIED·ready=false/ACCEPTANCE PASS 거부를 유지한다. 실외부/실회사·기기/10인/최종전환·최신main/전체회귀·원격push/배포는 미완료다.

## 30. 신뢰 이력 내보내기·별도 최신 지문으로 새 폴더 복구 (GW-READY-02 56차)

§29의 신뢰 원본을 보관용 패키지로 내보내고, 유실/손상 시 **기존 폴더를 보존한 채 새 폴더**에 정확한 원본을 재구성한다. 업무 DB/암호화 백업·복원 실행 결과를 복구하는 도구가 아니며, 실제 복원 도구의 PARTIAL을 바꾸지 않는다. 새 서명/키 권한·인수 완료 체크·업무 DB 스키마도 추가하지 않는다.

### 별도로 확인할 기준과 내보내기

담당자가 현재 정상 원장의 `status`에서 **ledgerId/revision/digest**를 확인하고, 장애/회수 뒤에도 최신 상태를 확인할 수 있는 별도 경로에 고정한다. status는 이번부터 ledgerId도 반환한다. 이 정보와 이후 출력 manifestDigest를 공급자/담당자별로 독립 보존할 필요가 있다. 패키지 안의 자기 지문을 복사해 최신 상태가 확인됐다고 간주하지 않는다. 최초 기준 설치 전 잃어버린 상태나 새 회수를 내보내기 전에 잃은 경우를 이전 패키지로 대신하지 않는다.

```sh
uv run --project backend python tools/gw_catalog_trust.py status
uv run --project backend python tools/gw_catalog_trust_transfer.py export \
  --directory /operator/trust-current --output /operator/trust-export-new \
  --expected-ledger-id CONFIRMED_LEDGER_UUID \
  --expected-revision CONFIRMED_LATEST_REVISION \
  --expected-digest CONFIRMED_LATEST_RECORD_SHA256
```

출력 폴더는 담당자가 준비한 새 빈0700 폴더다. 입력/출력/기존 원본 폴더는 서로 같거나 포함 관계이면 안 된다. 도구는 현재 원장 전체/현재 기준점을 확인하고, 확인한 최신 원장 ID/버전/지문과 일치할 때만 진행한다. 모든 기록을 **원래 바이트 그대로**0600 새 파일로 복사하고 원본을 다시 대조한 뒤 최종 `trust-manifest.json`을 쓴다. 중단 패키지에 manifest가 없으면 완성 자료가 아니며 새 빈 출력에서 다시 생성한다. 발행 개인키·현재 정상인 이관 연결/환경이 없어도 이미 보존한 회수 상태는 내보낼 수 있다.

`CATALOG_TRUST_EXPORT` v1 manifest는 anchor(version/ledgerId/revision/digest)와 연속1..최신 버전의 각 version/revision/digest/size만 포함한다. 파일 경로를 입력 문서에서 받지 않고 고정 이름 `trust-00000001-SHA256.json` 형식으로 계산한다. manifest 전체 지문은 출력의 manifestDigest다. 모든 이전 파일 지문이 다음 원본의 previousDigest에 연결돼 있고 별도 확인한 최신 원본 지문까지 일치해야 한다. 서명 검증/회사·키 용도/정상 은퇴 이관 자료의 별도 검증은 기존 환경 로더에서 계속 수행한다. 공개키·개인키/환경 설정·승인 파일/업무 데이터는 이 패키지에서 자동 설치하지 않는다.

### 유실/손상 원본 복구

```sh
uv run --project backend python tools/gw_catalog_trust_transfer.py receive \
  --directory /operator/trust-export-new --output /operator/trust-recovered-new \
  --existing-directory /operator/trust-damaged \
  --expected-ledger-id CONFIRMED_LEDGER_UUID \
  --expected-revision CONFIRMED_LATEST_REVISION \
  --expected-digest CONFIRMED_LATEST_RECORD_SHA256 \
  --expected-manifest-digest CONFIRMED_MANIFEST_SHA256
```

- 담당자는 유지보수 중 현재 신뢰 변경을 멈추고 최신 별도 기준을 확인한다. 도구는 기존 폴더를 잠그고, 남은 원본/현재·보류 기준점/이전 복구 영수증의 실제 바이트 지문을 고정한다. 기존 폴더의 이름에 **더 최신 버전**, 다른 원장/같은 버전의 다른 지문·중복 버전·현재/보류 기준점 분기가 있으면 과거 패키지로 복구하지 않는다. 기존에 더 최신 회수를 알고 있는데 `--new-host`나 다른 빈 폴더로 우회하지 않는다.
- 기존 원본이 다른 기기에 전혀 없는 **명시적 새 수신 환경**만 `--existing-directory` 대신 `--new-host`를 사용한다. 둘 중 하나만 필요하며, 별도 최신 기준의 진위/신선도는 여전히 담당자의 책임이다. 최신 원장 전체와 모든 복제본을 잃고 별도 최신 기준도 없다면 이 도구가 최신 상태를 추정하지 못한다.
- 새 복구 폴더에 확인한 원장/버전/지문·manifest 지문·기존 폴더/전체 지문 또는 새 환경 선언을 보류 기록 `.trust-receiving`으로 **입력 패키지 해석 전에** 보존한다. 그 폴더는 일반 API/기존 도구가 현재 신뢰로 읽지 못한다. 같은 보류를 다른 지문/기존 폴더·바뀐 원본 상태로 바꾸지 않는다.
- manifest 전체 지문/엄격 형식·파일 누락/추가/경로 주입/범위/버전·크기, 실제 모든 바이트/연속 버전·원장 ID/직전 연결/단조 상태 전이를 검사한다. 새로운 해시를 일관되게 계산한 자료도 REVOKED→ACTIVE/RETIRED, 은퇴 승인 후퇴/분기는 거부한다. 이전 정상 ACTIVE 자료를 현재 회수 대신 넣지 않는다.
- 기존 원본의 **확인된 버전/지문 파일명**은 완성 패키지의 같은 원본과 같아야 한다. 빈/잘린/바이트 손상 파일, 유실 원본·잘린 현재/보류 기준점은 그대로 기존 폴더에 두고 별도로 확인한 최신 전체 이력으로만 새 폴더를 구성한다. 잘못된 권한/링크/예상 밖 파일·알 수 없는 현재/보류 기준점 버전은 차단한다. 원본 없음/손상 사실이 실제 독립 최신 기준을 대신하지 않는다.
- 모든 새 기록을 배타 생성/fsync하고 저장된 원본/전이 전체와 기존 폴더 불변을 다시 대조한다. 복구 영수증 `.trust-received.json`→보류 현재 기준점/fsync→현재 기준점 원자 교체/fsync→수신 보류 제거/fsync 순서다. 영수증의 원장/버전·원본 지문은 이후 일반 조회에서도 검사하며 새 정상 원장 변경 때도 해당 원본을 보존한다. 새 영수증/원본·회수 상태를 바꾸거나 삭제하는 명령은 없다.

완료 출력은 ledgerId/revision/digest/manifestDigest·state=COMPLETE/ready=false, 종료0이다. **신뢰 원본 재구성 완료**이며 DB 복원 PASS/회사 운영 준비/독립 외부 저장소 인수 통과를 뜻하지 않는다. 실패는 비공개 경로/원본/키·전체 예외를 출력하지 않고 종료1이다. 입력 자료의 키/회사 설정을 신뢰하지 않으며 `admin` 로그인 이름도 OS 보존/회사 보안·서명 권한을 대신하지 않는다.

### 중단 재개와 서버 사용 전 확인

같은 원본/기존 폴더의 고정 바이트 상태·모든 확인 지문을 그대로 지정하고 receive에 `--resume`을 더한다. 이미 완성한 원본은 동일한 실제 바이트일 때만 재사용한다. 완성 영수증과 현재 원본을 다시 대조해 응답 유실 뒤 동일 완료를 확인할 수 있으나, 현재 원장이 더 전진했다면 과거 완료를 현재 결과로 반환하지 않는다. 같은 새 폴더에 두 실제 프로세스가 최초 수신을 동시에 실행하면 하나만 활성화할 수 있다.

잘린 복구 기록/영수증·보류 현재 기준점은 자동 덮어쓰기/삭제하지 않는다. 해당 폴더와 기존 손상 폴더를 함께 보존하고, 여전히 최신임을 별도 확인한 **같은 기준**으로 새 빈 복구 폴더를 준비한다. 원래 더 최신 상태/다른 분기를 발견한 경우에는 새 폴더 재시도로 우회하지 않는다. §29의 일반 resume으로 수신 보류를 우회할 수 없다.

도구는 `FS_GW_CATALOG_TRUST_DIRECTORY`/서버 환경을 자동 변경하지 않는다. 담당자는 복구 결과와 현재 회사별 공개키·목적/수명 상태·정확한 이관 원본이 맞는지 별도로 확인한 뒤 사용 경로를 전환해야 한다. 회수 상태 때문에 현재 승인 연결이 무효라면 복구가 끝나도 API는 CONFIG_REQUIRED/ready=false다. 설정을 맞추면 신뢰를 재검증하되 기존 최신 FAIL/PARTIAL/인수 실패와 새 대조·폐쇄 복원 조건은 계속 유지한다.

새 복구 영수증/수신 보류를 읽으려면 56차 검증기가 필요하다. 이전 검증기는 이를 구성 오류로 차단하며 도구가 운영 바이너리를 자동 업데이트하지 않는다. 기존 신뢰 원본/목록/이관 서명 형식은 유지한다.

최대4096원본·원본 하나256KiB/manifest2MiB와 기존 상태/승인 한도 중 먼저 도달한 제한이다. 원본 전체를 한 번에 메모리에 합치지 않으며 최대 약1GiB/최대 파일·장기 성능/독립 최신 기준 자동 갱신·공급자 원격 연결은 미검증이다. 패키지는 **신뢰 상태 원본**이며 예전 복구 진단 파일/손상 폴더 전체의 보관 사본은 아니다. 실패·손상 폴더는 별도 보존해야 한다. 같은 OS 계정 합성 폴더 수신/외부에서 확인했다고 가정한 시험 지문이며 독립 계정/장애 영역·WORM/공인 시각/전체 무누락을 증명하지 않는다. 실제 복원 PARTIAL·최종4조건 UNVERIFIED/ready=false·ACCEPTANCE PASS 거부 유지. 실외부/실회사10인·전체CI/회귀·최신main/원격push/배포는 남는다.


## 31. 운영 준비의 서버 차단 안내와 담당자별 다음 조치 (57차)

회사 GW의 **회사 운영 안내 → 운영 준비**에서 현재 회사·보안 관리자/감사 역할·연결 인원/예정 인원을 확인한다. 로그인 직후 자동으로 열리지 않으며 준비 미완료 때만 보이는 메뉴가 아니다. 로그인 ID `admin`은 개발자 관리자 기준으로 유지하되 회사 소속/활성 직원 연결·SECURITY_ADMIN 또는 AUDITOR와 서버 OS/서명 권한을 구분한다. ID 문자열로 권한을 부여하지 않는다.

상단 **지금 확인할 항목 → 담당자별 조치 확인**에서 서버 담당자, 회사 보안 관리자, 직원 본인의 다음 행동을 구분한다. 서버 차단은 검증 키/회사·용도/버전, 키 수명·이관 원본, 보존 설정 누락, 원본 읽기/대조 불가, 현재 설정 불일치, 기준점 반영 미완료, 복구 수신 진행 중의 허용된7코드로만 안내한다. 실패한 단계를 알리는 것이며 파일 손상의 구체 원인이나 독립 최신성을 확정하지 않는다. 경로·키·원본 오류 전문을 표시하지 않는다.

서버 작업은 §29–30에 따라 기존 원본/실패 폴더·최신 회수 상태를 보존한다. 회사 화면은 키를 설치하거나 백업/복구를 실행하지 않는다. **현재 상태 다시 점검**은 GET 조회이며 편집/증거 파일 선택/보관 검토/긴급 문서 입력 중에는 잠긴다. 실패하면 이전 결과를 숨기고 현재 회사·오류/재시도·업무 복귀 동선을 남긴다. 감사는 조회만 하며 직원 응답에는 서버 진단을 제공하지 않는다.

최근 실행 요약과 담당자 조치 뒤 **전환 조건 자세히 확인**에서12조건/미확인4조건의 근거를 펼친다. 회사 선택을 유지한 직원·조직/업무 복귀 링크와 정적 도움말을 이용한다. 안내를 읽거나 재점검해도 ready=false·실제 복원 PARTIAL/최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부는 유지한다. 공급자 미정/독립 보관·전체 수집/회수·실회사10인/최종 전환은 별도다.

로컬5362 미리보기는 별도 합성 DB이며 현재 저장된 합성 로그인과 개발 환경의 admin을 혼동하지 않는다.57차 읽기 점검에서는 해당 DB에 admin 계정이 없고 저장된 합성 계정/접속 정보는 현재 DB와 일치했다. 실제 계정 생성/이름 변경·비밀번호 초기화·DB 초기화를 수행하지 않았다. 접속 비밀은 무시되는 로컬 자료로만 관리하며 문서/Git/화면 증거에 싣지 않는다.

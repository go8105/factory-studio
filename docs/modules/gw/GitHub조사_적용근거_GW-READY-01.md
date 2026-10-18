# GitHub 조사와 적용 근거 · GW-READY-01

2026-10-18 조사. 제품 전체를 가져오거나 코드를 복사하지 않고, 공개 구현의 흐름/권한/복구 원칙을 현재 Factory Studio 구조와 비교했다. 아래 commit은 조사 시점 GitHub API에서 확인한 기본 브랜치 기준이다. 라이선스가 다른 프로젝트를 통째로 내장하는 안이 아니다. 실제 라이브러리는 구현 단계에서 버전·해시·라이선스·Python3.14 호환성을 고정하고 검증한다.

| 원본과 확인 위치 | 관찰 | 이번 적용 판단 |
|---|---|---|
| [EGroupware InfoLog](https://github.com/EGroupware/egroupware/blob/cfc7e9b8676e893105159ee3916316cfcafcb6cd/doc/REST-CalDAV-CardDAV/Infolog.md) | 소유자·담당·참조자와 읽기/쓰기 항목을 구분 | 역할별 행동과 편집 가능 항목을 화면에 명시. 업무 관리 자체는 독립 Flow에 두며 InfoLog를 GW에 이식하지 않음 |
| [Frappe HRMS 휴가 신청](https://github.com/frappe/hrms/blob/44e80d64686ae07297095930e5102aadaf034bc8/hrms/hr/doctype/leave_application/leave_application.py) | 신청자와 승인자 검증을 업무 처리에 포함 | 본인 업무와 관리자 처리를 분리하고 서버에서 확인. 이번 설계로 HR/PWA 휴가 정책을 변경하지 않음 |
| [Frappe workflow](https://github.com/frappe/frappe/blob/f22f9316eb2f6a0f7d619adc4f64f069a66c2fcc/frappe/model/workflow.py) | 상태 전환과 승인 접근을 서버에서 판단 | 버튼을 숨기는 것만으로 권한 처리하지 않음. 기존 GW 현재 주체/배정/버전 검증을 보존 |
| [authentik 기본 인증 흐름](https://github.com/goauthentik/authentik/blob/0bf3eb26917c7fdbee26b48ea8cc0145f3bdc9d5/blueprints/default/flow-default-authentication-flow.yaml) | 식별/비밀번호/MFA 검증 등을 단계로 구성 | 사용자에게는 다음 행동을 한 단계씩 제시. 비밀번호만 통과한 중간 상태와 업무 세션을 분리 |
| [Nextcloud 백업 코드 저장·사용](https://github.com/nextcloud/server/blob/5563121bd20fb1676185f5a237056110625b8c8c/apps/twofactor_backupcodes/lib/Service/BackupCodeStorage.php) | 무작위 코드 hash 저장, 재발급 시 이전 코드 교체, 미사용 상태를 원자적으로 소비 | 코드8개1회 표시·원문 재조회 없음·동시 사용1건 성공을 자체 계약으로 설계. PHP/AGPL 코드를 제품에 복사하지 않음 |
| [PyOTP 보안 점검 항목](https://github.com/pyauth/pyotp/blob/cc156832fa9f3d5af7fb9e4e6b86b29dfc5b69f1/README.rst) | HTTPS·비밀 보호·OTP 재사용 거부·시도 제한을 요구 | TOTP 계산 성공만으로 MFA 완료로 보지 않음. 사용 step과 실패 횟수/키 관리/실기기 검증 포함 |
| [Authlib 저장소](https://github.com/authlib/authlib/tree/8a308fc39c378c1090608903a09318a4267f418a), [공식 OIDC/웹 클라이언트 문서](https://docs.authlib.org/en/latest/oauth2/client/web/) | OAuth/OIDC 클라이언트·검증 라이브러리 제공 | 서명/JWT 검증 직접 구현 대신 검증 라이브러리 사용 계획. 실제 IdP subject의 명시 연결과 공급자 MFA 정책은 우리 서버가 별도로 판단 |
| [W3C 오류 식별 안내](https://www.w3.org/WAI/WCAG22/Understanding/error-identification.html) | 오류 항목과 오류 내용을 사용자가 식별할 수 있게 안내 | 입력 옆 오류+요약·포커스·입력 유지. 이 참고만으로 WCAG 준수 인증을 주장하지 않음 |

## 가져오지 않는 것

- Frappe ERP 전체·타 솔루션 업무 DB, Nextcloud 전체 파일 시스템/공유 계층, 새로운 TEAM 구조를 이식하지 않는다. 현재 core 회사/HR 읽기/GW S 범위와 독립 Flow를 유지한다.
- authentik 서버 도입을 필수로 강요하지 않는다. 10인 회사의 기본 인증은 기존 계정+TOTP이며 외부 SSO가 필요해지면 OIDC로 연결한다.
- GitHub의 화면·정책·라이선스를 그대로 복제하지 않는다. 사용자의 한국어 업무·기존 버튼 명칭·권한과 실제 운영 비용을 기준으로 새 설계를 만든다.
- 라이브러리 지원과 실제 제품 구현/배포·회사 인수를 혼동하지 않는다. 이 문서는 조사·설계 근거이며 우리 제품의 MFA 구현 완료 증거가 아니다.

## 현재 코드와의 차이

현재 core는 scrypt 비밀번호 검증, opaque 세션 token/hash, CSRF·cookie, 현재 사용자/회사 소속 확인을 제공한다. GW는 명시적 직원 연결/역할·현재 객체 ACL·성공 영수증 전 권한·회수/재배정 검증을 구현했다. MFA 중간 challenge·TOTP 비밀 암호화·백업 코드/제한 복구 세션·OIDC subject 연결·운영 정책/서명 증거·운영 준비 화면은 아직 없다.

현재 검증 결과는 [GW-COMPANY-05](../../agent/GW_WMS통합_인수검증_GW-COMPANY-05.md)를 따르고, 이번 제안과 제품 기능을 섞지 않는다. 설계와 검토용 UI를 확인한 뒤 [전체 구현 계약](실사용_보안운영_UI_통합설계_GW-READY-01.md)의 A~E를 한 구현 ID로 진행한다.

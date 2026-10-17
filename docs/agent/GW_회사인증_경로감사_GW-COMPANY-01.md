# GW 회사 인증 전환 경로 감사표 · GW-COMPANY-01

2026-10-17, 제품 기준 e02097d. router.py AST로 추출한 기존63경로. 이 표는 구현 후 확인할 권한 범위이며 현재 회사 모드 검증 통과 결과가 아니다. `/api/v1/gw/projects`는 독립 Flow의 별도 라우터다.

모든 경로 공통: 회사 소속/활성계정/세션/모듈/바인딩을 재검사하고 personId·actingPersonId 가장을 차단한다. 관리자는 명시적 역할, 업무는 객체 ACL을 적용한다. 목록·count·별칭·receipt도 포함한다. 회사 모드 신규 경로는 통합 설계 §4에 별도 명세했다.

| 메서드 | 경로 | 회사 모드의 추가 검사 | 코드 근거 |
|---|---|---|---|
| GET | `/dashboard` | 본인 ACL로 목록·count 집계 | `router.py:36 dashboard` |
| GET | `/sources` | 회사 첫 범위 GENERAL만: 원천 선택/상세 미공개, 직접 요청도 차단 | `router.py:41 sources` |
| GET | `/sources/{kind}/{document_no}` | 회사 첫 범위 GENERAL만: 원천 선택/상세 미공개, 직접 요청도 차단 | `router.py:63 source` |
| GET | `/documents` | 기안자/유효 참여자/처리 이력/읽기grant; 변경은 해당 업무 역할 | `router.py:72 documents` |
| GET | `/posts` | 작성자/회사·현재 직접 소속; 공지는 BOARD_PUBLISHER | `router.py:101 posts` |
| GET | `/people` | 최소 디렉터리; ORG_ADMIN 변경, alias도 동일 적용 | `router.py:131 list_people` |
| GET | `/people-options` | 최소 디렉터리; ORG_ADMIN 변경, alias도 동일 적용 | `router.py:142 people_options` |
| GET | `/people/{id}` | 최소 디렉터리; ORG_ADMIN 변경, alias도 동일 적용 | `router.py:148 get_people` |
| POST | `/people` | 최소 디렉터리; ORG_ADMIN 변경, alias도 동일 적용 | `router.py:153 post_people` |
| PATCH | `/people/{id}` | 최소 디렉터리; ORG_ADMIN 변경, alias도 동일 적용 | `router.py:160 patch_people` |
| GET | `/routes` | 활성 디렉터리 조회·ROUTE_ADMIN 변경 | `router.py:171 list_routes` |
| GET | `/routes/{id}` | 활성 디렉터리 조회·ROUTE_ADMIN 변경 | `router.py:182 get_routes` |
| POST | `/routes` | 활성 디렉터리 조회·ROUTE_ADMIN 변경 | `router.py:187 post_routes` |
| PATCH | `/routes/{id}` | 활성 디렉터리 조회·ROUTE_ADMIN 변경 | `router.py:194 patch_routes` |
| GET | `/documents/{id}` | 기안자/유효 참여자/처리 이력/읽기grant; 변경은 해당 업무 역할 | `router.py:205 get_documents` |
| POST | `/documents` | 기안자/유효 참여자/처리 이력/읽기grant; 변경은 해당 업무 역할 | `router.py:210 post_documents` |
| PATCH | `/documents/{id}` | 기안자/유효 참여자/처리 이력/읽기grant; 변경은 해당 업무 역할 | `router.py:217 patch_documents` |
| GET | `/posts/{id}` | 작성자/회사·현재 직접 소속; 공지는 BOARD_PUBLISHER | `router.py:228 get_posts` |
| POST | `/posts` | 작성자/회사·현재 직접 소속; 공지는 BOARD_PUBLISHER | `router.py:233 post_posts` |
| PATCH | `/posts/{id}` | 작성자/회사·현재 직접 소속; 공지는 BOARD_PUBLISHER | `router.py:240 patch_posts` |
| POST | `/documents/{id}/select-route` | 기안자/유효 참여자/처리 이력/읽기grant; 변경은 해당 업무 역할 | `router.py:251 documents_select_route` |
| POST | `/documents/{id}/refresh-source` | 기안자/유효 참여자/처리 이력/읽기grant; 변경은 해당 업무 역할 | `router.py:262 documents_refresh_source` |
| POST | `/documents/{id}/submit` | 기안자/유효 참여자/처리 이력/읽기grant; 변경은 해당 업무 역할 | `router.py:269 documents_submit` |
| POST | `/documents/{id}/approve` | 기안자/유효 참여자/처리 이력/읽기grant; 변경은 해당 업무 역할 | `router.py:276 documents_approve` |
| POST | `/documents/{id}/reject` | 기안자/유효 참여자/처리 이력/읽기grant; 변경은 해당 업무 역할 | `router.py:283 documents_reject` |
| POST | `/documents/{id}/withdraw` | 기안자/유효 참여자/처리 이력/읽기grant; 변경은 해당 업무 역할 | `router.py:290 documents_withdraw` |
| POST | `/documents/{id}/resubmit` | 기안자/유효 참여자/처리 이력/읽기grant; 변경은 해당 업무 역할 | `router.py:297 documents_resubmit` |
| POST | `/posts/{id}/publish` | 작성자/회사·현재 직접 소속; 공지는 BOARD_PUBLISHER | `router.py:304 posts_publish` |
| POST | `/posts/{id}/withdraw` | 작성자/회사·현재 직접 소속; 공지는 BOARD_PUBLISHER | `router.py:311 posts_withdraw` |
| POST | `/posts/{id}/correct` | 작성자/회사·현재 직접 소속; 공지는 BOARD_PUBLISHER | `router.py:318 posts_correct` |
| GET | `/authority-rules` | POLICY_ADMIN 변경; 일반 직원에게 적용 최소값만 | `router.py:325 authority_rules` |
| POST | `/authority-rules` | POLICY_ADMIN 변경; 일반 직원에게 적용 최소값만 | `router.py:331 create_authority` |
| PATCH | `/authority-rules/{id}` | POLICY_ADMIN 변경; 일반 직원에게 적용 최소값만 | `router.py:346 patch_authority` |
| DELETE | `/authority-rules/{id}` | POLICY_ADMIN 변경; 일반 직원에게 적용 최소값만 | `router.py:361 delete_authority` |
| GET | `/delegations` | 본인 위임·활성 상대/기간·회수; 관리 전체목록은 명시 역할 | `router.py:368 list_delegations` |
| POST | `/delegations` | 본인 위임·활성 상대/기간·회수; 관리 전체목록은 명시 역할 | `router.py:373 create_delegation` |
| POST | `/delegations/{id}/revoke` | 본인 위임·활성 상대/기간·회수; 관리 전체목록은 명시 역할 | `router.py:384 revoke_delegation` |
| POST | `/documents/{id}/consent` | 기안자/유효 참여자/처리 이력/읽기grant; 변경은 해당 업무 역할 | `router.py:395 consent_document` |
| POST | `/documents/{id}/oppose` | 기안자/유효 참여자/처리 이력/읽기grant; 변경은 해당 업무 역할 | `router.py:402 oppose_document` |
| POST | `/documents/{id}/reference` | 기안자/유효 참여자/처리 이력/읽기grant; 변경은 해당 업무 역할 | `router.py:409 reference_document` |
| GET | `/hr-preview` | ORG_ADMIN·HR 읽기 계약·명시적 스냅샷, 자동 바인딩 없음 | `router.py:416 hr_preview` |
| POST | `/import-hr` | ORG_ADMIN·HR 읽기 계약·명시적 스냅샷, 자동 바인딩 없음 | `router.py:421 import_hr` |
| GET | `/people-master` | 최소 디렉터리; ORG_ADMIN 변경, alias도 동일 적용 | `router.py:432 people_master` |
| POST | `/people-master` | 최소 디렉터리; ORG_ADMIN 변경, alias도 동일 적용 | `router.py:443 create_people_master` |
| PATCH | `/people-master/{id}` | 최소 디렉터리; ORG_ADMIN 변경, alias도 동일 적용 | `router.py:450 edit_people_master` |
| GET | `/comments` | 부모 객체 현재 ACL+본인 댓글 변경·삭제 | `router.py:492 comments` |
| GET | `/calendar` | 공개/작성/명시 참석·본인 참석 응답 | `router.py:514 calendar` |
| GET | `/calendar/{id}` | 공개/작성/명시 참석·본인 참석 응답 | `router.py:528 calendar_detail` |
| GET | `/notifications` | 본인 수신+대상 현재 ACL, 제목/건수도 필터 | `router.py:535 notifications` |
| GET | `/channels` | 활성 채널 참여·본인 전송/읽음/탈퇴, 탈퇴 후 replay 차단 | `router.py:549 channels` |
| GET | `/channels/{id}/messages` | 활성 채널 참여·본인 전송/읽음/탈퇴, 탈퇴 후 replay 차단 | `router.py:554 messages` |
| POST | `/calendar/{id}/respond` | 공개/작성/명시 참석·본인 참석 응답 | `router.py:569 respond_calendar` |
| POST | `/comments` | 부모 객체 현재 ACL+본인 댓글 변경·삭제 | `router.py:584 create_comment` |
| PATCH | `/comments/{id}` | 부모 객체 현재 ACL+본인 댓글 변경·삭제 | `router.py:591 edit_comment` |
| POST | `/comments/{id}/delete` | 부모 객체 현재 ACL+본인 댓글 변경·삭제 | `router.py:602 delete_comment` |
| POST | `/calendar` | 공개/작성/명시 참석·본인 참석 응답 | `router.py:609 create_calendar` |
| PATCH | `/calendar/{id}` | 공개/작성/명시 참석·본인 참석 응답 | `router.py:616 edit_calendar` |
| POST | `/calendar/{id}/cancel` | 공개/작성/명시 참석·본인 참석 응답 | `router.py:627 cancel_calendar` |
| POST | `/notifications/{id}/read` | 본인 수신+대상 현재 ACL, 제목/건수도 필터 | `router.py:634 read_notification` |
| POST | `/channels` | 활성 채널 참여·본인 전송/읽음/탈퇴, 탈퇴 후 replay 차단 | `router.py:641 create_channel` |
| POST | `/channels/{id}/leave` | 활성 채널 참여·본인 전송/읽음/탈퇴, 탈퇴 후 replay 차단 | `router.py:648 leave_channel` |
| POST | `/channels/{id}/read` | 활성 채널 참여·본인 전송/읽음/탈퇴, 탈퇴 후 replay 차단 | `router.py:655 read_channel` |
| POST | `/channels/{id}/messages` | 활성 채널 참여·본인 전송/읽음/탈퇴, 탈퇴 후 replay 차단 | `router.py:662 send_message` |

import { RetentionReviews } from "./RetentionReviews";
import { OperatingEvidence } from "./OperatingEvidence";
import { useState } from "react";
import { EmergencyKit } from "./EmergencyKit";
import { Link } from "react-router-dom";
import {
  ErrorNotice,
  Field,
  FormPanel,
  Loading,
  PageTitle,
  useDiscardGuard,
} from "../shared/components";
import { GwLink, SelectedPeople, useGet, useRole, useSend } from "./common";
import "./Operations.css";
type Policy = {
  expectedPeople: number;
  expectedDepartments: number;
  responsiblePersonId: string;
  backupIntervalMinutes: number;
  rpoMinutes: number;
  rtoMinutes: number;
  documentReviewMonths: number;
  auditReviewMonths: number;
  backupKeepDays: number;
  reason: string;
};
type State = {
  administrator: boolean;
  canEdit: boolean;
  version: number;
  rolloutState: string;
  connectedPeople: number;
  mfaPeople: number;
  policy: Policy | null;
  revisionNo: number | null;
  ready: boolean;
  blockers: string[];
  launchGate?: {
    ready: boolean;
    confirmedCount: number;
    blockedCount: number;
    unverifiedCount: number;
    checks: {
      code: string;
      label: string;
      state: "CONFIRMED" | "BLOCKED" | "UNVERIFIED";
      detail: string;
      nextAction: string;
      acceptanceScope?: string;
      requiredEvidence?: string[];
    }[];
  };
  backupRestoreCollection?: {
    result: "PARTIAL" | "BLOCKED";
    source: "LATEST_REGISTRATIONS";
    backupRestorePairVerified: boolean;
    restoreMeasurements?: {
      rowHashesMatch: boolean | null;
      foreignKeysValid: boolean | null;
      sessionsInvalidated: boolean | null;
      revocationsReapplied: boolean | null;
      twoAccountChecks: boolean | null;
      lossWindowSeconds: number | null;
      elapsedSeconds: number | null;
      restoreDiagnostics: {
        databaseClosed: boolean;
        dbRevisionMatches: boolean;
        checkpointRestrictionsApplied: boolean;
        checkpointCompletenessConfirmed: boolean;
        journalCandidateIntents: number;
        journalUnconfirmedIntents: number;
        journalQuarantinedScopes: number;
        executionObservation?: {
          observedAt: string;
          unrevokedSessions: number;
          pendingChallenges: number;
          coreViolations: number;
          gwViolations: number;
          hrViolations: number;
          journalUserViolations: number;
        };
      } | null;
    } | null;
  };
  evidenceChecks?: {
    kind: string;
    label: string;
    state: string;
    detail: string;
    restoreRecheck?: {
      checkedAt: string;
      result: "PARTIAL" | "BLOCKED";
      targetMeasured: boolean;
      stateMatchesExecution: boolean | null;
      reason: "MEASURED" | "MEASUREMENT_UNAVAILABLE";
      measurement?: {
        unrevokedSessions: number;
        pendingChallenges: number;
        coreViolations: number;
        gwViolations: number;
        hrViolations: number;
        journalUserViolations: number;
        connectionLimitZero: boolean;
        publicConnectRevoked: boolean;
      };
    };
    journalObservation?: {
      observedAt: string;
      scopeRecords: number;
      auditConfirmed: number;
      abortConfirmed: number;
      unresolvedRecords: number;
      missingTransactionProofs: number;
    };
  }[];
  nextAction?: string;
  emergencyKit?: { prepared: boolean; expiresAt: string | null };
};
const fields: [
  keyof Omit<Policy, "reason" | "responsiblePersonId">,
  string,
  number,
  number,
][] = [
  ["expectedPeople", "예정 직원 수", 1, 10000],
  ["expectedDepartments", "예정 부서 수", 1, 1000],
  ["backupIntervalMinutes", "백업 간격 (분)", 5, 1440],
  ["rpoMinutes", "허용 손실 시간 (분)", 1, 1440],
  ["rtoMinutes", "복구 목표 시간 (분)", 15, 10080],
  ["documentReviewMonths", "일반 문서 검토 기한 (개월)", 1, 120],
  ["auditReviewMonths", "감사 기록 검토 기한 (개월)", 1, 120],
  ["backupKeepDays", "백업 보관 기간 (일)", 7, 365],
];
type GateCheck = NonNullable<State["launchGate"]>["checks"][number];
const gateLabels = {
  CONFIRMED: "확인됨",
  BLOCKED: "조치 필요",
  UNVERIFIED: "미확인",
};
const evidenceLabels: Record<string, string> = {
  RECORDED_PASS: "등록된 통과",
  PARTIAL: "일부 확인",
  FAILED: "실패",
  INVALID: "대조 실패",
  STALE: "현재 기준 재확인",
  MISSING: "기록 없음",
  LEGACY_UNVERIFIED: "원본 확인 필요",
  CONFIG_REQUIRED: "서버 설정 필요",
  POLICY_REQUIRED: "운영 기준 필요",
};
function CheckAction({ code }: { code: string }) {
  if (code === "PEOPLE" || code === "RESPONSIBLE")
    return <GwLink to="/gw/people">직원·권한 확인</GwLink>;
  if (code === "DEPARTMENTS")
    return <GwLink to="/gw/organization">조직 확인</GwLink>;
  if (code === "MFA")
    return <Link to="/account/security">내 계정 보안 확인</Link>;
  if (code === "POLICY")
    return <a href="#gw-operating-policy">운영 기준으로 이동</a>;
  if (["BACKUP", "RESTORE", "ACCEPTANCE"].includes(code))
    return <a href="#gw-operating-evidence">실행 기록으로 이동</a>;
  return <Link to="/help/gw/operations">인수 절차 도움말</Link>;
}
function GateRows({ checks }: { checks: GateCheck[] }) {
  return (
    <dl className="gw-check-list">
      {checks.map((check) => (
        <div key={check.code}>
          <dt>
            <span className="gw-check-state" data-state={check.state}>
              {check.label} · {gateLabels[check.state]}
            </span>
          </dt>
          <dd>
            <p>{check.detail}</p>
            {check.nextAction && (
              <p className="gw-next-action">{check.nextAction}</p>
            )}
            {check.state !== "CONFIRMED" && <CheckAction code={check.code} />}
            {!!check.requiredEvidence?.length && (
              <details className="gw-check-evidence">
                <summary>필요한 인수 근거</summary>
                <p>{check.acceptanceScope}</p>
                <ul>
                  {check.requiredEvidence.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
                <p>이 안내는 제출된 증거나 완료 승인이 아닙니다.</p>
              </details>
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}
export function Operations() {
  const role = useRole();
  const state = useGet<State>(role.companyId ? "/operations" : null);
  const [editing, setEditing] = useState(false);
  const [kitPending, setKitPending] = useState(false);
  const [recoveryOpen, setRecoveryOpen] = useState(false);
  const [retentionEditing, setRetentionEditing] = useState(false);
  if (!role.companyId)
    return (
      <section className="gw-operations">
        <PageTitle id="GW 운영" title="운영 준비" help="gw/operations" />
        <p>
          회사 공간을 선택한 뒤 이용하세요. 개인 체험에는 회사 운영 기준을
          저장하지 않습니다.
        </p>
        <GwLink to="/gw/dashboard">GW 업무로 돌아가기</GwLink>
      </section>
    );
  if (state.error)
    return <ErrorNotice error={state.error} retry={state.reload} />;
  if (!state.data) return <Loading />;
  const data = state.data;
  const blocked =
    data.launchGate?.checks.filter((c) => c.state === "BLOCKED") ?? [];
  const unverified =
    data.launchGate?.checks.filter((c) => c.state === "UNVERIFIED") ?? [];
  const confirmed =
    data.launchGate?.checks.filter((c) => c.state === "CONFIRMED") ?? [];
  const next = blocked[0] ?? unverified[0];
  return (
    <section className="gw-operations">
      <header className="gw-operations-heading">
        <PageTitle id="GW 운영" title="운영 준비" help="gw/operations" />
        <p>선택 회사의 계정·보관·복구 상태를 점검하는 GW 관리 화면입니다.</p>
        <div className="gw-operations-links">
          <GwLink to="/gw/dashboard">GW 업무로 돌아가기</GwLink>
          <GwLink to="/gw/pending">내 결재함</GwLink>
          <Link to="/account/security">내 계정 보안 확인</Link>
        </div>
      </header>
      {!data.administrator ? (
        <p>{data.nextAction}</p>
      ) : (
        <>
          <section
            className="gw-operating-overview"
            aria-labelledby="gw-readiness-title"
          >
            <div>
              <h2 id="gw-readiness-title">
                {data.ready
                  ? "운영 전환 조건을 확인했습니다"
                  : "아직 운영 준비 중입니다"}
              </h2>
              <p className="gw-company-name">
                {role.companyName ?? `회사 #${role.companyId}`} ·{" "}
                {data.canEdit ? "보안 관리자" : "감사 · 조회 전용"}
              </p>
              <p>
                본인 연결 {data.connectedPeople}명
                {data.policy ? ` / 예정 ${data.policy.expectedPeople}명` : ""} ·
                인증 앱 등록 {data.mfaPeople}명
              </p>
              <p>
                직원 연결과 인증 앱 등록 수는 현재 상태입니다. 대표 업무와
                실환경 인수는 별도로 확인합니다.
              </p>
            </div>
            <div className="gw-operating-next">
              <h3>지금 확인할 항목</h3>
              {next ? (
                <>
                  <strong>{next.label}</strong>
                  <p>{next.nextAction || next.detail}</p>
                  <CheckAction code={next.code} />
                </>
              ) : (
                <p>아래 운영 기준과 최근 실행 결과를 확인하세요.</p>
              )}
            </div>
          </section>
          <nav
            className="gw-operations-sections"
            aria-label="운영 준비 항목 바로가기"
          >
            <a href="#gw-launch-conditions">전환 조건</a>
            <a href="#gw-operating-evidence">실행 증거</a>
            <a href="#gw-operating-policy">보관·복구 기준</a>
            <a href="#gw-retention">보관 검토</a>
            {data.canEdit && <a href="#gw-account-recovery">계정 복구</a>}
          </nav>
          <section
            id="gw-launch-conditions"
            className="gw-operating-section"
            tabIndex={-1}
            aria-labelledby="gw-launch-title"
          >
            <h2 id="gw-launch-title">운영 전환 조건</h2>
            <p>
              현재 결과와 필요한 조치를 확인하세요. 체크 표시로 완료 처리하지
              않습니다.
            </p>
            {data.launchGate ? (
              <>
                <p className="gw-operating-counts">
                  확인됨 {data.launchGate.confirmedCount}개 · 조치 필요{" "}
                  {data.launchGate.blockedCount}개 · 미확인{" "}
                  {data.launchGate.unverifiedCount}개
                </p>
                {blocked.length > 0 && <GateRows checks={blocked} />}
                {unverified.length > 0 && (
                  <>
                    <h3>실환경 근거가 필요한 조건</h3>
                    <GateRows checks={unverified} />
                  </>
                )}
                {confirmed.length > 0 && (
                  <details className="gw-confirmed-conditions">
                    <summary>확인된 조건 {confirmed.length}개 보기</summary>
                    <GateRows checks={confirmed} />
                  </details>
                )}
              </>
            ) : (
              <ul>
                {data.blockers.map((message) => (
                  <li key={message}>{message}</li>
                ))}
              </ul>
            )}
          </section>
          <section
            id="gw-operating-evidence"
            className="gw-operating-section"
            tabIndex={-1}
            aria-label="실행 증거와 등록"
          >
            {data.evidenceChecks && (
              <>
                <h2>실행 증거 확인</h2>
                <p>
                  각 종류의 최근 등록 결과입니다. 등록된 통과만으로 운영을
                  시작하지 않습니다.
                </p>
                <dl className="gw-check-list">
                  {data.evidenceChecks.map((check) => (
                    <div key={check.kind}>
                      <dt>
                        {check.label}
                        <small>
                          {evidenceLabels[check.state] ?? "결과 확인 필요"}
                        </small>
                      </dt>
                      <dd>
                        {check.detail}
                        {check.restoreRecheck && (
                          <details>
                            <summary>복원본 최근 재관측</summary>
                            <p>
                              관측 시각:{" "}
                              {new Date(
                                check.restoreRecheck.checkedAt,
                              ).toLocaleString("ko-KR")}
                            </p>
                            <p>
                              서명 관측의 유효 기한은 15분입니다. 관측 이후의
                              상태를 연속 감시하지 않습니다.
                            </p>
                            {check.restoreRecheck.measurement ? (
                              <>
                                <p>
                                  회수되지 않은 세션{" "}
                                  {
                                    check.restoreRecheck.measurement
                                      .unrevokedSessions
                                  }
                                  건 · 남은 인증 요청{" "}
                                  {
                                    check.restoreRecheck.measurement
                                      .pendingChallenges
                                  }
                                  건
                                </p>
                                <p>
                                  제한 불일치: 공통{" "}
                                  {
                                    check.restoreRecheck.measurement
                                      .coreViolations
                                  }
                                  건 · GW{" "}
                                  {
                                    check.restoreRecheck.measurement
                                      .gwViolations
                                  }
                                  건 · 인사{" "}
                                  {
                                    check.restoreRecheck.measurement
                                      .hrViolations
                                  }
                                  건 · 변경 기록 사용자{" "}
                                  {
                                    check.restoreRecheck.measurement
                                      .journalUserViolations
                                  }
                                  건
                                </p>
                                <p>
                                  접속수 0 제한{" "}
                                  {check.restoreRecheck.measurement
                                    .connectionLimitZero
                                    ? "확인"
                                    : "미통과"}{" "}
                                  · 공개 접속 회수{" "}
                                  {check.restoreRecheck.measurement
                                    .publicConnectRevoked
                                    ? "확인"
                                    : "미통과"}
                                </p>
                                {check.restoreRecheck.stateMatchesExecution ===
                                  false && (
                                  <p>
                                    복원 직후와 상태 지문이 다릅니다. 제한 대조
                                    결과와 변경 원인을 함께 확인하세요.
                                  </p>
                                )}
                              </>
                            ) : (
                              <p>
                                복원본을 측정하지 못했습니다. 연결 상태를
                                조사하고 새 관측을 실행하세요. 측정값을 0건으로
                                간주하지 않습니다.
                              </p>
                            )}
                            <p>
                              운영 담당자가 원인을 확인한 뒤 새 관측과 인수
                              점검을 등록하세요. 전체 권한 회수·실회사 인수·운영
                              전환은 별도 확인이 필요합니다.
                            </p>
                          </details>
                        )}
                        {check.journalObservation && (
                          <details>
                            <summary>회사 변경 기록 관측 내용</summary>
                            <p>
                              관측 시각:{" "}
                              {new Date(
                                check.journalObservation.observedAt,
                              ).toLocaleString("ko-KR")}
                            </p>
                            <p>
                              대조 대상 {check.journalObservation.scopeRecords}
                              건 · DB 감사 확인{" "}
                              {check.journalObservation.auditConfirmed}건 · 거래
                              취소 확인{" "}
                              {check.journalObservation.abortConfirmed}건
                            </p>
                            <p>
                              미확인 거래{" "}
                              {check.journalObservation.unresolvedRecords}건 ·
                              거래 근거 없음{" "}
                              {
                                check.journalObservation
                                  .missingTransactionProofs
                              }
                              건
                            </p>
                            <p>
                              {check.state === "FAILED"
                                ? "운영 담당자가 미확인 기록을 조사한 뒤 새 관측과 인수 점검을 등록해야 합니다."
                                : "관측한 회사·세대의 기록만 확인했습니다. 전체 변경 수집·권한 회수와 실제 회사 인수는 별도로 확인합니다."}
                            </p>
                          </details>
                        )}
                      </dd>
                    </div>
                  ))}
                </dl>
              </>
            )}
            {data.backupRestoreCollection && (
              <section aria-label="백업·복원 연결 점검">
                <h3>백업·복원 연결 점검</h3>
                <p>
                  {data.backupRestoreCollection.backupRestorePairVerified
                    ? "최근 등록한 백업·복원 증거가 같은 백업을 가리킵니다. 일부 확인이며 운영 인수 완료는 아닙니다."
                    : "최근 등록한 백업·복원 증거의 연결을 확인하지 못했습니다. 위 실행 증거 결과와 등록한 파일 쌍을 확인하세요."}
                </p>
                <p>
                  더 최근 미통과 기록을 과거 성공 기록으로 대신하지 않습니다.
                </p>
                <details>
                  <summary>최근 복원 검사 내용</summary>
                  {data.backupRestoreCollection.restoreMeasurements ? (
                    <>
                      <p>
                        최근 복원 실행의 서명된 검사 결과입니다. 전체 권한
                        회수와 회사 업무 인수는 별도로 확인합니다.
                      </p>
                      <dl>
                        {(
                          [
                            ["rowHashesMatch", "데이터 지문 일치"],
                            ["foreignKeysValid", "참조 관계 검사"],
                            ["sessionsInvalidated", "이전 세션 무효화"],
                            ["revocationsReapplied", "전체 권한 회수 확인"],
                            ["twoAccountChecks", "관리자·직원 업무 확인"],
                          ] as const
                        ).map(([field, label]) => (
                          <div key={field}>
                            <dt>{label}</dt>
                            <dd>
                              {data.backupRestoreCollection
                                ?.restoreMeasurements?.[field] === true
                                ? "확인"
                                : data.backupRestoreCollection
                                      ?.restoreMeasurements?.[field] === false
                                  ? "미충족"
                                  : "기록 없음"}
                            </dd>
                          </div>
                        ))}
                      </dl>
                      {data.backupRestoreCollection.restoreMeasurements
                        .restoreDiagnostics ? (
                        <p>
                          복원 DB 격리:{" "}
                          {data.backupRestoreCollection.restoreMeasurements
                            .restoreDiagnostics.databaseClosed
                            ? "확인"
                            : "미충족"}{" "}
                          · 권한 대조 완전성:{" "}
                          {data.backupRestoreCollection.restoreMeasurements
                            .restoreDiagnostics.checkpointCompletenessConfirmed
                            ? "확인"
                            : "미확인"}{" "}
                          · 미확인 변경 기록{" "}
                          {
                            data.backupRestoreCollection.restoreMeasurements
                              .restoreDiagnostics.journalUnconfirmedIntents
                          }
                          건 · 격리 범위{" "}
                          {
                            data.backupRestoreCollection.restoreMeasurements
                              .restoreDiagnostics.journalQuarantinedScopes
                          }
                          개
                        </p>
                      ) : (
                        <p>세부 격리·변경 기록 진단이 없는 이전 형식입니다.</p>
                      )}
                      {data.backupRestoreCollection.restoreMeasurements
                        .restoreDiagnostics?.executionObservation && (
                        <section aria-label="복원 직후 제한 재대조">
                          <h4>복원 직후 제한 재대조</h4>
                          <p>
                            관측 시각:{" "}
                            {new Date(
                              data.backupRestoreCollection.restoreMeasurements
                                .restoreDiagnostics.executionObservation
                                .observedAt,
                            ).toLocaleString("ko-KR")}
                          </p>
                          <p>
                            회수되지 않은 세션{" "}
                            {
                              data.backupRestoreCollection.restoreMeasurements
                                .restoreDiagnostics.executionObservation
                                .unrevokedSessions
                            }
                            건 · 진행 중 인증 요청{" "}
                            {
                              data.backupRestoreCollection.restoreMeasurements
                                .restoreDiagnostics.executionObservation
                                .pendingChallenges
                            }
                            건
                          </p>
                          <p>
                            제한 불일치: 공통 인증{" "}
                            {
                              data.backupRestoreCollection.restoreMeasurements
                                .restoreDiagnostics.executionObservation
                                .coreViolations
                            }
                            건 · GW{" "}
                            {
                              data.backupRestoreCollection.restoreMeasurements
                                .restoreDiagnostics.executionObservation
                                .gwViolations
                            }
                            건 · HR{" "}
                            {
                              data.backupRestoreCollection.restoreMeasurements
                                .restoreDiagnostics.executionObservation
                                .hrViolations
                            }
                            건 · 변경 기록 계정{" "}
                            {
                              data.backupRestoreCollection.restoreMeasurements
                                .restoreDiagnostics.executionObservation
                                .journalUserViolations
                            }
                            건
                          </p>
                          <p>
                            백업과 최신 권한 대조에 기록된 제한을 복원 직후 다시
                            확인한 결과입니다. 현재 복원본 상태·전체 권한
                            회수·실제 회사 업무 인수를 확인한 것은 아닙니다.
                          </p>
                        </section>
                      )}
                    </>
                  ) : (
                    <p>
                      현재 기준으로 원본 서명과 등록 내용을 확인한 복원 검사
                      기록이 없습니다.
                    </p>
                  )}
                </details>
              </section>
            )}

            <OperatingEvidence
              onRecorded={state.reload}
              canEdit={data.canEdit}
              disabled={editing || kitPending || retentionEditing}
            />
          </section>
          <section
            id="gw-operating-policy"
            className="gw-operating-section"
            tabIndex={-1}
            aria-labelledby="gw-policy-title"
          >
            <div className="gw-operating-section-heading">
              <h2 id="gw-policy-title">
                보관·복구 기준{" "}
                {data.revisionNo ? `· ${data.revisionNo}번째 버전` : "· 미적용"}
              </h2>
              {data.canEdit && (
                <button
                  disabled={kitPending || retentionEditing}
                  onClick={() => setEditing(true)}
                >
                  운영 기준 검토·적용
                </button>
              )}
            </div>
            {data.policy ? (
              <dl className="gw-policy-values">
                {fields.map(([key, label]) => (
                  <div key={key}>
                    <dt>{label}</dt>
                    <dd>{data.policy![key]}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p>
                10인 회사 기본안을 검토하고 책임자와 사유를 정해 적용하세요.
                기본값은 실제 회사 정책이나 복구 성능 보장이 아닙니다.
              </p>
            )}
            <p>
              보관 기한은 검토 시점입니다. 원본 문서를 자동 삭제하지 않습니다.
            </p>
            {!data.canEdit && (
              <p>
                현재는 조회 권한입니다. 기준 변경은 GW 보안 관리자에게
                요청하세요.
              </p>
            )}
          </section>
          <section
            id="gw-retention"
            className="gw-operating-section"
            tabIndex={-1}
            aria-label="보관 검토 관리"
          >
            <RetentionReviews
              canEdit={data.canEdit}
              disabled={editing || kitPending}
              onEditingChange={setRetentionEditing}
              onSettingsVersionChange={(version) =>
                state.setData({ ...data, version })
              }
            />
          </section>
          {data.canEdit && (
            <section
              id="gw-account-recovery"
              className="gw-operating-section"
              tabIndex={-1}
              aria-label="계정 복구 관리"
            >
              <details
                open={recoveryOpen || kitPending}
                onToggle={(event) => setRecoveryOpen(event.currentTarget.open)}
              >
                <summary>본인 긴급 복구 문서 관리</summary>
                <EmergencyKit
                  status={data.emergencyKit}
                  reload={state.reload}
                  disabled={editing || retentionEditing}
                  onPendingChange={setKitPending}
                />
              </details>
            </section>
          )}
          {editing && (
            <PolicyEdit
              state={data}
              close={() => setEditing(false)}
              done={() => {
                setEditing(false);
                state.reload();
              }}
            />
          )}
        </>
      )}
    </section>
  );
}

function PolicyEdit({
  state,
  close,
  done,
}: {
  state: State;
  close: () => void;
  done: () => void;
}) {
  const role = useRole();
  const initial: Policy = state.policy ?? {
    expectedPeople: 10,
    expectedDepartments: 1,
    responsiblePersonId: role.person,
    backupIntervalMinutes: 30,
    rpoMinutes: 60,
    rtoMinutes: 240,
    documentReviewMonths: 36,
    auditReviewMonths: 12,
    backupKeepDays: 30,
    reason: "",
  };
  const [form, setForm] = useState({ ...initial, reason: "" });
  const [agree, setAgree] = useState(false);
  const [validation, setValidation] = useState("");
  const request = useSend();
  const guard = useDiscardGuard(
    JSON.stringify(form) !== JSON.stringify({ ...initial, reason: "" }) ||
      agree,
  );
  return (
    <FormPanel
      title="보관·복구 기준 검토"
      guard={guard}
      onClose={close}
      onSubmit={async (e) => {
        e.preventDefault();
        setValidation("");
        if (form.backupIntervalMinutes >= form.rpoMinutes) {
          setValidation("백업 간격은 허용 손실 시간보다 짧아야 합니다.");
          return;
        }
        if (
          await request.send("/operating-policies", "POST", {
            expectedVersion: state.version,
            policy: form,
          })
        )
          done();
      }}
      actions={
        <>
          <button disabled={request.pending || !agree}>새 버전으로 적용</button>
          <button
            disabled={request.pending}
            type="button"
            onClick={() => guard.guard(close)}
          >
            취소
          </button>
        </>
      }
    >
      <p>
        현재 버전 {state.revisionNo ?? "없음"} → 새 버전. 적용 전에{" "}
        <Link to="/account/security" target="_blank">
          내 계정 보안
        </Link>
        에서 본인 확인을 마쳐 주세요. 5분이 지나면 다시 확인해야 합니다.
      </p>
      <ErrorNotice error={request.error} />
      {validation && <p role="alert">{validation}</p>}
      {fields.map(([key, label, min, max]) => (
        <Field
          key={key}
          label={label}
          type="number"
          min={min}
          max={max}
          step={1}
          required
          value={Number.isNaN(form[key]) ? "" : form[key]}
          disabled={request.pending}
          onChange={(e) =>
            setForm({
              ...form,
              [key]: e.target.value === "" ? NaN : Number(e.target.value),
            })
          }
        />
      ))}
      <label>
        복구 책임자
        <select
          required
          value={form.responsiblePersonId}
          disabled={request.pending}
          onChange={(e) =>
            setForm({ ...form, responsiblePersonId: e.target.value })
          }
        >
          <option value="">선택하세요</option>
          {role.people
            .filter((p) => p.isActive)
            .map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} · {p.code}
              </option>
            ))}
          <SelectedPeople ids={[form.responsiblePersonId]} />
        </select>
      </label>
      <Field
        label="적용 사유"
        required
        minLength={2}
        maxLength={500}
        value={form.reason}
        disabled={request.pending}
        onChange={(e) => setForm({ ...form, reason: e.target.value })}
      />
      <p>
        이미 확정한 버전은 덮어쓰지 않습니다. 기한을 줄여도 문서를 즉시 삭제하지
        않습니다. 실제 백업·복원 결과와 담당자 보관 장소 확인은 별도입니다.
      </p>
      <label>
        <input
          type="checkbox"
          checked={agree}
          disabled={request.pending}
          onChange={(e) => setAgree(e.target.checked)}
        />
        변경 내용과 영향을 검토했습니다
      </label>
    </FormPanel>
  );
}

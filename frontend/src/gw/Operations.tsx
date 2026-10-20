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
import { SelectedPeople, useGet, useRole, useSend } from "./common";
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
  };
  evidenceChecks?: {
    kind: string;
    label: string;
    state: string;
    detail: string;
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
export function Operations() {
  const role = useRole();
  const state = useGet<State>(role.companyId ? "/operations" : null);
  const [editing, setEditing] = useState(false);
  const [kitPending, setKitPending] = useState(false);
  const [retentionEditing, setRetentionEditing] = useState(false);
  if (!role.companyId)
    return (
      <section>
        <h1>운영 준비</h1>
        <p>
          회사 공간을 선택한 뒤 이용하세요. 개인 체험에는 회사 운영 기준을
          저장하지 않습니다.
        </p>
      </section>
    );
  if (state.error)
    return <ErrorNotice error={state.error} retry={state.reload} />;
  if (!state.data) return <Loading />;
  const data = state.data;
  return (
    <section className="card">
      <PageTitle id="GW 운영" title="운영 준비" help="gw/operations" />
      <p>
        운영 준비는 실제 연결·보안·검증 결과로 판단합니다. 체크 표시를 눌러 완료
        처리하는 화면이 아닙니다.
      </p>
      <Link to="/account/security">내 계정 보안 확인</Link>
      {!data.administrator ? (
        <p>{data.nextAction}</p>
      ) : (
        <>
          <h2>아직 운영 준비 중입니다</h2>
          <p>
            본인 연결 {data.connectedPeople}명 · 인증 앱 등록 {data.mfaPeople}명
          </p>
          {data.launchGate ? (
            <>
              <h3>운영 전환 조건</h3>
              <p>
                확인됨 {data.launchGate.confirmedCount}개 · 조치 필요{" "}
                {data.launchGate.blockedCount}개 · 미확인{" "}
                {data.launchGate.unverifiedCount}개
              </p>
              <dl>
                {data.launchGate.checks.map((check) => (
                  <div key={check.code}>
                    <dt>
                      {check.label} ·{" "}
                      {
                        {
                          CONFIRMED: "확인됨",
                          BLOCKED: "조치 필요",
                          UNVERIFIED: "미확인",
                        }[check.state]
                      }
                    </dt>
                    <dd>
                      {check.detail}
                      {check.nextAction && <p>{check.nextAction}</p>}
                      {!!check.requiredEvidence?.length && (
                        <details>
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
            </>
          ) : (
            <ul>
              {data.blockers.map((message) => (
                <li key={message}>{message}</li>
              ))}
            </ul>
          )}
          {data.evidenceChecks && (
            <>
              <h3>실행 증거 확인</h3>
              <p>
                각 종류의 최근 등록 결과입니다. 등록된 통과만으로 운영을
                시작하지 않습니다.
              </p>
              <dl>
                {data.evidenceChecks.map((check) => (
                  <div key={check.kind}>
                    <dt>{check.label}</dt>
                    <dd>{check.detail}</dd>
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
              <p>더 최근 미통과 기록을 과거 성공 기록으로 대신하지 않습니다.</p>
            </section>
          )}
          {data.canEdit && (
            <EmergencyKit
              status={data.emergencyKit}
              reload={state.reload}
              disabled={editing || retentionEditing}
              onPendingChange={setKitPending}
            />
          )}
          <h2>
            보관·복구 기준{" "}
            {data.revisionNo ? `· ${data.revisionNo}번째 버전` : "· 미적용"}
          </h2>
          {data.policy ? (
            <dl>
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
          {data.canEdit && (
            <button
              disabled={kitPending || retentionEditing}
              onClick={() => setEditing(true)}
            >
              운영 기준 검토·적용
            </button>
          )}
          <OperatingEvidence
            onRecorded={state.reload}
            canEdit={data.canEdit}
            disabled={editing || kitPending || retentionEditing}
          />
          <RetentionReviews
            canEdit={data.canEdit}
            disabled={editing || kitPending}
            onEditingChange={setRetentionEditing}
            onSettingsVersionChange={(version) =>
              state.setData({ ...data, version })
            }
          />
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

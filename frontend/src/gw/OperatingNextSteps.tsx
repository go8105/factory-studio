import { Link } from "react-router-dom";
import { GwLink } from "./common";

const issues = {
  VERIFIER_CONFIGURATION: [
    "실행 증거 검증 설정을 확인해야 합니다",
    "검증 키·허용 회사/용도 또는 제품 버전을 확인하지 못했습니다.",
    "서버 운영 담당자가 현재 회사의 검증 키·허용 범위와 제품·DB 버전을 대조해야 합니다.",
  ],
  CATALOG_LIFECYCLE: [
    "목록 키의 교체·회수 근거를 확인해야 합니다",
    "현재 키 상태 또는 고정한 이관 원본을 검증하지 못했습니다.",
    "현재 회수 상태와 정확한 이관 원본·허용 범위를 확인하세요. 옛 승인으로 회수를 되돌리지 마세요.",
  ],
  TRUST_STORE_REQUIRED: [
    "목록 신뢰 이력의 보존 설정이 필요합니다",
    "현재 목록 권한에 필요한 보존 경로가 설정되지 않았습니다.",
    "기존 보존 이력의 위치와 최신 기준을 확인하세요. 사용하던 원장을 새 빈 원장으로 대신하지 마세요.",
  ],
  TRUST_STORE_UNAVAILABLE: [
    "보존한 신뢰 원본을 읽거나 대조하지 못했습니다",
    "보존 경로·권한 또는 원본과 현재 기준점의 대조를 완료하지 못했습니다.",
    "손상 원본을 보존하고 별도로 확인한 최신 기준과 대조하세요. 복구가 필요하면 새 폴더에 같은 원본을 재구성하세요.",
  ],
  TRUST_SETTINGS_MISMATCH: [
    "현재 키 설정과 보존 이력이 다릅니다",
    "현재 설정을 보존한 최신 키 상태·승인 연결과 일치시키지 못했습니다.",
    "현재 설정과 보존한 회수·은퇴 상태를 대조하세요. 정상 변경은 현재 기준으로 설치하고 과거 설정으로 되돌리지 마세요.",
  ],
  TRUST_UPDATE_PENDING: [
    "신뢰 이력의 기록 마무리가 필요합니다",
    "새 기록의 현재 기준점 반영이 끝나지 않았습니다.",
    "완성한 같은 원본과 확인한 지문으로 기록을 마무리하세요. 잘린 원본을 덮거나 이전 기준점으로 초기화하지 마세요.",
  ],
  TRUST_RECOVERY_PENDING: [
    "신뢰 이력 복구가 아직 진행 중입니다",
    "현재 보존 폴더에 완료되지 않은 수신·복구 기록이 있습니다.",
    "같은 최신 기준·패키지·기존 원본으로 복구를 마무리하세요. 손상 폴더를 보존하고 완료 후 현재 권한을 다시 대조하세요.",
  ],
} as const;
export function configurationFor(
  issue: { code: string } | undefined,
  checks?: { state: string }[],
) {
  if (!issue && !checks?.some((c) => c.state === "CONFIG_REQUIRED"))
    return null;
  const code =
    issue && Object.hasOwn(issues, issue.code)
      ? (issue.code as keyof typeof issues)
      : "VERIFIER_CONFIGURATION";
  const [title, detail, nextAction] = issues[code];
  return { code, title, detail, nextAction };
}
export function CheckAction({ code }: { code: string }) {
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
type Check = {
  code: string;
  label: string;
  detail: string;
  nextAction: string;
};
export function OperatingNextSteps({
  issue,
  checks,
  recovery,
  canEdit,
  disabled,
  refresh,
  refreshRef,
}: {
  issue: ReturnType<typeof configurationFor>;
  checks: Check[];
  recovery?: { nextAction: string };
  canEdit: boolean;
  disabled: boolean;
  refresh: () => void;
  refreshRef: React.RefObject<HTMLButtonElement | null>;
}) {
  const tasks: {
    key: string;
    owner: string;
    title: string;
    detail: string;
    action: React.ReactNode;
  }[] = [];
  if (issue)
    tasks.push({
      key: "server",
      owner: "서버 운영 담당자",
      title: issue.title,
      detail: issue.nextAction,
      action: (
        <Link to="/help/gw/operations#서버-점검이-필요할-때">
          서버 점검 도움말
        </Link>
      ),
    });
  else if (recovery)
    tasks.push({
      key: "recovery",
      owner: "서버 운영 담당자",
      title: "실행 실패 후 새 근거 확인",
      detail: recovery.nextAction,
      action: <a href="#gw-operating-evidence">실행 기록과 재점검 순서</a>,
    });
  const company = checks.find((c) =>
    ["PEOPLE", "RESPONSIBLE", "DEPARTMENTS", "POLICY"].includes(c.code),
  );
  if (company)
    tasks.push({
      key: "company",
      owner: "회사 보안 관리자",
      title: company.label,
      detail: company.nextAction || company.detail,
      action: <CheckAction code={company.code} />,
    });
  const account = checks.find((c) => c.code === "MFA");
  if (account)
    tasks.push({
      key: "account",
      owner: "직원 본인 · 회사 보안 관리자",
      title: account.label,
      detail: account.nextAction || account.detail,
      action: <CheckAction code="MFA" />,
    });
  if (tasks.length === 0 && checks[0])
    tasks.push({
      key: "acceptance",
      owner: ["BACKUP", "RESTORE"].includes(checks[0].code)
        ? "서버 운영 담당자"
        : "회사 운영 책임자",
      title: checks[0].label,
      detail: checks[0].nextAction || checks[0].detail,
      action: <CheckAction code={checks[0].code} />,
    });
  return (
    <section
      id="gw-next-actions"
      className="gw-operating-section gw-next-steps"
      tabIndex={-1}
      aria-labelledby="gw-next-actions-title"
    >
      <div className="gw-operating-section-heading">
        <h2 id="gw-next-actions-title">담당자별 다음 조치</h2>
        <button
          ref={refreshRef}
          type="button"
          disabled={disabled}
          onClick={refresh}
        >
          현재 상태 다시 점검
        </button>
      </div>
      <p>
        {canEdit
          ? "회사에서 할 일과 서버에서 할 일을 나눠 확인하세요."
          : "조회 전용 화면입니다. 변경이 필요한 항목은 아래 담당자에게 전달하세요."}{" "}
        다시 점검은 현재 결과를 조회하며 백업·복구를 실행하지 않습니다.
      </p>
      {disabled && (
        <p role="status">
          입력 중인 내용을 마치거나 취소한 뒤 다시 점검하세요.
        </p>
      )}
      {issue && (
        <p className="gw-config-explanation">
          {issue.detail} 검증하지 못한 이전 성공은 현재 근거로 표시하지
          않습니다.
        </p>
      )}
      {tasks.length ? (
        <ol className="gw-owner-tasks">
          {tasks.map((task) => (
            <li key={task.key}>
              <span className="gw-task-owner">{task.owner}</span>
              <div>
                <h3>{task.title}</h3>
                <p>{task.detail}</p>
                {task.action}
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <p>아래 전환 조건과 최근 실행 기록을 확인하세요.</p>
      )}
      <details>
        <summary>이 화면의 권한과 점검 범위</summary>
        <p>
          운영 준비는 회사 공간에서 보안 관리자와 감사 역할에 제공됩니다. 감사
          역할은 조회만 하며 직원은 본인 계정 보안을 확인합니다. 개발자 관리자
          아이디가 admin이어도 회사 보안 권한이나 서버 작업 권한이 자동으로
          생기지 않습니다.
        </p>
        <p>
          신뢰 이력 복구와 실행 증거 등록은 운영 전환 승인이 아닙니다. 외부 독립
          보관·전체 권한 회수·실회사 인수는 별도로 확인합니다.
        </p>
      </details>
    </section>
  );
}

import { useEffect, useState } from "react";
import { useSession } from "../app/session";
import { ErrorNotice, Field } from "../shared/components";
import { useSend } from "./common";
export type EmergencyDocument = {
  version: 1;
  userId: string;
  companyId: string;
  generationId: string;
  personId: string;
  kitId: string;
  kitSecret: string;
};
type Issued = { kit: EmergencyDocument; expiresAt: string };
export function EmergencyKit({
  status,
  reload,
}: {
  status?: { prepared: boolean; expiresAt: string | null };
  reload: () => void;
}) {
  const { setNavigationBlocked } = useSession();
  const [issued, setIssued] = useState<Issued>();
  const [reason, setReason] = useState("");
  const [consent, setConsent] = useState(false);
  const [downloaded, setDownloaded] = useState(false);
  const [stored, setStored] = useState(false);
  const request = useSend();
  useEffect(() => {
    if (!issued) return;
    setNavigationBlocked(true);
    const guard = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", guard);
    return () => {
      setNavigationBlocked(false);
      window.removeEventListener("beforeunload", guard);
    };
  }, [issued, setNavigationBlocked]);
  function download() {
    if (!issued) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(issued.kit, null, 2)], {
        type: "application/json",
      }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "factory-studio-emergency-kit.json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    setDownloaded(true);
  }
  if (issued)
    return (
      <section className="card" aria-label="긴급 복구 문서 보관">
        <h2>긴급 복구 문서를 지금 보관하세요</h2>
        <p>
          원문은 이 화면에서 한 번만 저장할 수 있습니다. 비밀번호·휴대폰·일반
          복구 코드와 다른 안전한 장소에 보관하세요. 서버 운영자의 일회 승인과
          본인 비밀번호가 있어야 사용할 수 있습니다.
        </p>
        <p>문서 기한: {new Date(issued.expiresAt).toLocaleString("ko-KR")}</p>
        <button onClick={download}>긴급 복구 문서 파일 저장</button>
        {downloaded && (
          <p role="status">
            파일 저장을 요청했습니다. 실제 파일과 별도 보관 장소를 확인하세요.
          </p>
        )}
        <label>
          <input
            type="checkbox"
            checked={stored}
            disabled={!downloaded}
            onChange={(e) => setStored(e.target.checked)}
          />
          파일을 안전한 별도 장소에 보관했습니다
        </label>
        <button
          disabled={!stored}
          onClick={() => {
            setIssued(undefined);
            setNavigationBlocked(false);
            setReason("");
            setConsent(false);
            setStored(false);
            setDownloaded(false);
            reload();
          }}
        >
          보관 확인하고 닫기
        </button>
      </section>
    );
  return (
    <section className="card">
      <h2>관리자 긴급 복구 준비</h2>
      <p>
        {status?.prepared
          ? "유효한 긴급 복구 문서가 준비되어 있습니다."
          : "본인 계정의 유효한 긴급 복구 문서가 없습니다."}
      </p>
      {status?.expiresAt && (
        <p>
          최근 문서 기한: {new Date(status.expiresAt).toLocaleString("ko-KR")}
        </p>
      )}
      <p>
        인증 앱과 일반 복구 코드를 모두 잃었을 때 사용합니다. 새 문서를 발급하면
        이 회사의 이전 문서와 아직 사용하지 않은 승인 파일이 무효화됩니다. 계정
        보안 변경 후에는 새 문서가 필요합니다.
      </p>
      <p>
        먼저 내 계정 보안에서 본인 확인을 마치세요. 문서 재발급은 10분에
        3번까지입니다.
      </p>
      <ErrorNotice error={request.error} />
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const result = await request.send<Issued>("/emergency-kit", "POST", {
            reason,
          });
          if (result) {
            setIssued(result);
            setDownloaded(false);
            setStored(false);
          }
        }}
      >
        <Field
          label="긴급 복구 문서 발급 사유"
          required
          minLength={2}
          maxLength={500}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          disabled={request.pending}
        />
        <label>
          <input
            type="checkbox"
            checked={consent}
            disabled={request.pending}
            onChange={(e) => setConsent(e.target.checked)}
          />
          이전 문서·미사용 승인 파일 회수와 별도 보관 필요를 확인했습니다
        </label>
        <button disabled={request.pending || !consent} type="submit">
          본인 긴급 복구 문서 새로 발급
        </button>
      </form>
    </section>
  );
}

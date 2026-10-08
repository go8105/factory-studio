import { Link, useSearchParams } from "react-router-dom";
import { useSession } from "../app/session";
import "./CadCam.css";
export default function CadCam() {
  const { session } = useSession();
  const [params] = useSearchParams();
  const admin =
    session?.actorKind === "MEMBER" && session.roles.includes("ADMIN");
  const soap = admin && params.get("view") === "soap";
  const part = params.get("view") === "part";
  const nc = params.get("view") === "nc";
  const scope = `${session!.workspaceId}:${session!.generationId}`;
  return (
    <section className="cad-cam-page" aria-label="CAD·CAM 작업실">
      <div className="cad-cam-heading">
        <div>
          <h1>CAD·CAM</h1>
          <p>
            {nc
              ? "NC 파일은 브라우저 메모리에서만 읽으며 서버에 전송하지 않습니다."
              : "직접 설계하고 가공 과정을 확인하세요. 설계는 이 공간의 브라우저에 저장됩니다."}
          </p>
          {!soap && (
            <Link
              to={`/help/portal/${nc ? "nc-review" : part ? "part-design" : "cad-cam"}`}
            >
              사용 도움말
            </Link>
          )}
        </div>
        <nav aria-label="CAD·CAM 화면">
          <Link
            to="/cad-cam"
            className={!soap && !part && !nc ? "active" : ""}
            aria-current={!soap && !part && !nc ? "page" : undefined}
          >
            설계·가공 편집기
          </Link>
          <Link
            to="/cad-cam?view=part"
            className={part ? "active" : ""}
            aria-current={part ? "page" : undefined}
          >
            3D 부품 설계
          </Link>
          <Link
            to="/cad-cam?view=nc"
            className={nc ? "active" : ""}
            aria-current={nc ? "page" : undefined}
          >
            NC 경로 검토
          </Link>
          {admin && (
            <Link
              to="/cad-cam?view=soap"
              className={soap ? "active" : ""}
              aria-current={soap ? "page" : undefined}
            >
              비누 그라인더 POC
            </Link>
          )}
        </nav>
      </div>
      <iframe
        key={`${scope}:${soap}:${part}:${nc}`}
        allow={nc ? "microphone" : undefined}
        title={
          soap
            ? "비누 그라인더 POC"
            : part
              ? "3D 부품 설계"
              : nc
                ? "NC 경로 검토"
                : "CAD·CAM 편집기"
        }
        src={`${soap ? "/api/v1/cad/admin/soap-poc/soap-poc.html" : part ? "/cad-cam-app/part-design.html" : nc ? "/cad-cam-app/nc-review.html" : "/cad-cam-app/index.html"}?embedded=1&scope=${encodeURIComponent(scope)}${admin ? "&poc=1" : ""}`}
      />
    </section>
  );
}

import { Navigate, useLocation } from "react-router-dom";
export function LegacyFlowRedirect({ page }: { page: string }) {
  const { search, hash } = useLocation();
  return <Navigate replace to={`/work-os/${page}${search}${hash}`} />;
}

// CMMS 화면이 쓰는 조회 훅. 경로 하나를 불러오고, 경로나 reload가 바뀌면 다시 부른다.
import { useEffect, useState } from "react";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import { CMMS } from "./common";
export { fieldErrors, moduleOff } from "../shared/hooks";

export function useGet<T>(path: string | null) {
  const { fail } = useSession();
  const [data, setData] = useState<T>();
  const [error, setError] = useState<unknown>();
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    setError(undefined);
    api<T>(`${CMMS}${path}`, { signal: controller.signal })
      .then((r) => !controller.signal.aborted && setData(r.data))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [path, tick]);
  return { data, error, reload: () => setTick((n) => n + 1) };
}

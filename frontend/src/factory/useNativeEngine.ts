import { useEffect, useState } from "react";
import { useSession } from "../app/session";
import { NativeEngine } from "./nativeEngine";
export function useNativeEngine() {
  const { session, fail } = useSession();
  const [engine] = useState(() => new NativeEngine(session?.csrfToken, fail));
  useEffect(() => {
    engine.csrf = session?.csrfToken;
    engine.fail = fail;
  }, [engine, session?.csrfToken, fail]);
  useEffect(() => () => engine.cancel(), [engine]);
  return engine;
}

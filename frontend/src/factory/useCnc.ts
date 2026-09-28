import { useEffect, useReducer } from "react";
import { cncReducer, initialCnc } from "./cnc";
export function useCnc(enabled: boolean) {
  const [state, dispatch] = useReducer(cncReducer, undefined, initialCnc);
  useEffect(() => {
    const pause = () => {
      if (document.hidden) dispatch({ type: "pause" });
    };
    document.addEventListener("visibilitychange", pause);
    return () => document.removeEventListener("visibilitychange", pause);
  }, []);
  useEffect(() => {
    if (!enabled || state.mode !== "running") return;
    let previous = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      if (!document.hidden)
        dispatch({ type: "tick", seconds: (now - previous) / 1000 });
      previous = now;
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [enabled, state.mode]);
  return [state, dispatch] as const;
}

import { browserEngine, type Engine } from "./inspectionRun";
import type { InspectionRequest } from "./inspection";
export type PlcFault = "INSPECTION_TIMEOUT" | "ACK_TIMEOUT" | "ENGINE_ERROR";
export type PlcState = {
  phase: "ready" | "busy" | "done" | "fault";
  inspectionId: string | null;
  result: "OK" | "NG" | null;
  fault: PlcFault | null;
  trigger: boolean;
  done: boolean;
  inspection: { request: InspectionRequest; output: Output } | null;
  injection: "none" | "delay" | "missingAck";
  events: {
    at: string;
    inspectionId: string | null;
    event: string;
    signals: ReturnType<typeof plcSignals>;
  }[];
};
type Output = Awaited<ReturnType<Engine>>;
export function plcSignals(state: PlcState) {
  return {
    Vision_Ready_Req: true,
    Trigger_In: state.trigger,
    Vision_Ready: state.phase === "ready",
    Vision_Busy: state.phase === "busy",
    Inspection_Done: state.done,
    Result_OK: state.result === "OK",
    Result_NG: state.result === "NG",
    Interlock: state.phase === "fault",
  };
}
export class PlcHandshake {
  enabled = false;
  state: PlcState = {
    phase: "ready",
    inspectionId: null,
    result: null,
    fault: null,
    trigger: false,
    done: false,
    injection: "none",
    inspection: null,
    events: [],
  };
  private listeners = new Set<() => void>();
  private timers = new Set<ReturnType<typeof setTimeout>>();
  private generation = 0;
  private pending:
    | {
        resolve: (output: Output) => void;
        reject: (error: Error) => void;
        output?: Output;
      }
    | undefined;
  private deadline = 0;
  constructor(
    private engine: Engine = browserEngine,
    private cancelEngine: () => void = () => {},
  ) {}
  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => {
      this.listeners.delete(fn);
    };
  };
  snapshot = () => this.state;
  private update(patch: Partial<PlcState>, event: string) {
    const next = { ...this.state, ...patch };
    this.state = {
      ...next,
      events: [
        ...next.events,
        {
          at: new Date().toISOString(),
          inspectionId: next.inspectionId,
          event,
          signals: plcSignals(next),
        },
      ].slice(-200),
    };
    this.listeners.forEach((fn) => fn());
  }
  private later(fn: () => void, ms: number) {
    const timer = setTimeout(() => {
      this.timers.delete(timer);
      fn();
    }, ms);
    this.timers.add(timer);
  }
  private clear() {
    this.generation++;
    this.timers.forEach(clearTimeout);
    this.timers.clear();
  }
  inject(injection: PlcState["injection"]) {
    this.update({ injection }, `다음 검사 장애 예약: ${injection}`);
  }
  clearLog() {
    this.update(
      { events: [], inspectionId: null, inspection: null },
      "새 배치",
    );
  }
  duplicateTrigger() {
    this.update({}, "중복 트리거 무시: 새 검사는 Ready에서만 수락");
  }
  execute: Engine = (
    request: InspectionRequest,
    inspectionId = crypto.randomUUID(),
  ) => {
    if (this.state.phase !== "ready") {
      this.duplicateTrigger();
      return Promise.reject(new Error("PLC not ready"));
    }
    const injection = this.state.injection;
    this.clear();
    const token = this.generation;
    const snapshot = structuredClone(request);
    return new Promise<Output>((resolve, reject) => {
      this.pending = { resolve, reject };
      this.deadline = performance.now() + 300;
      this.update(
        {
          phase: "busy",
          inspectionId,
          trigger: true,
          done: false,
          result: null,
          fault: null,
          inspection: null,
          injection: "none",
        },
        "Trigger ON → Busy ON (Recipe_ID=RUN_SNAPSHOT)",
      );
      this.later(() => this.fail("INSPECTION_TIMEOUT"), 300);
      this.later(
        () => {
          void Promise.resolve()
            .then(() => this.engine(snapshot, inspectionId))
            .then(
              (output) => {
                if (token !== this.generation) return;
                if (performance.now() >= this.deadline) {
                  this.fail("INSPECTION_TIMEOUT");
                  return;
                }
                this.clear();
                if (!this.pending) return;
                this.pending.output = structuredClone(output);
                this.deadline = performance.now() + 1000;
                this.update(
                  {
                    phase: "done",
                    done: true,
                    result: output.result.status,
                    inspection: {
                      request: snapshot,
                      output: structuredClone(output),
                    },
                  },
                  `Busy OFF → Result_${output.result.status} + Done ON`,
                );
                this.later(() => this.fail("ACK_TIMEOUT"), 1000);
                if (injection !== "missingAck")
                  this.later(() => this.acknowledge(), 120);
              },
              () => {
                if (token === this.generation) this.fail("ENGINE_ERROR");
              },
            );
        },
        injection === "delay" ? 450 : 80,
      );
    });
  };
  acknowledge() {
    if (this.state.phase !== "done" || !this.pending?.output) return;
    if (performance.now() >= this.deadline) {
      this.fail("ACK_TIMEOUT");
      return;
    }
    const { resolve, output } = this.pending;
    this.clear();
    this.pending = undefined;
    this.update(
      { phase: "ready", trigger: false, done: false, result: null },
      "PLC 결과 확인 → Trigger OFF → Done/Result OFF → Ready",
    );
    resolve(output);
  }
  private fail(fault: PlcFault) {
    this.cancelEngine();
    const reject = this.pending?.reject;
    this.clear();
    this.pending = undefined;
    this.update(
      { phase: "fault", fault },
      `${fault} → Interlock ON, 다음 검사 차단`,
    );
    reject?.(new Error(fault));
  }
  cancel() {
    this.cancelEngine();
    const reject = this.pending?.reject;
    this.clear();
    this.pending = undefined;
    if (this.state.phase !== "fault" && this.state.phase !== "ready")
      this.update(
        { phase: "ready", trigger: false, done: false, result: null },
        "거래 취소 → 신호 해제",
      );
    reject?.(new Error("PLC cancelled"));
  }
  reset() {
    this.cancel();
    this.update(
      {
        phase: "ready",
        trigger: false,
        done: false,
        result: null,
        fault: null,
        inspectionId: null,
        inspection: null,
        injection: "none",
      },
      "PLC 리셋 → Ready (자동 재개 없음)",
    );
  }
}

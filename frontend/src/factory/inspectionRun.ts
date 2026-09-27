import {
  inspect,
  type InspectionRequest,
  type InspectionResult,
  type Recipe,
  type Sample,
} from "./inspection";
export const sequence: readonly Sample[] = Array.from(
  { length: 5 },
  () => ["normal", "foreign", "normal", "lighting"] as Sample[],
).flat();
export type RunRecord = {
  inspectionId: string;
  sequence: number;
  startedAt: string;
  completedAt: string;
  inspectionMs: number;
  request: InspectionRequest;
  result: InspectionResult;
};
export type RunState = {
  version: 1;
  runId: string;
  status: "idle" | "running" | "paused" | "completed" | "stopped" | "error";
  recipe: Recipe;
  intervalMs: number;
  records: RunRecord[];
  error: string | null;
};
export type Engine = (
  request: InspectionRequest,
) => Promise<{ result: InspectionResult; inspectionMs: number }>;
const browserEngine: Engine = async (request) => {
  const start = performance.now();
  const result = inspect(request);
  return { result, inspectionMs: performance.now() - start };
};
export class InspectionRun {
  state: RunState;
  private listeners = new Set<() => void>();
  private timer: ReturnType<typeof setTimeout> | undefined;
  private generation = 0;
  private pending = false;
  constructor(
    recipe: Recipe,
    private engine: Engine = browserEngine,
  ) {
    this.state = {
      version: 1,
      runId: "",
      status: "idle",
      recipe: { ...recipe },
      intervalMs: 500,
      records: [],
      error: null,
    };
  }
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  snapshot = () => this.state;
  private update(patch: Partial<RunState>) {
    this.state = { ...this.state, ...patch };
    this.listeners.forEach((fn) => fn());
  }
  start(recipe: Recipe, intervalMs: number) {
    if (this.state.status === "running" || this.state.status === "paused")
      return;
    this.cancel();
    this.update({
      runId: crypto.randomUUID(),
      status: "running",
      recipe: { ...recipe },
      intervalMs,
      records: [],
      error: null,
    });
    void this.next();
  }
  pause() {
    if (this.state.status === "running") {
      clearTimeout(this.timer);
      this.update({ status: "paused" });
    }
  }
  resume() {
    if (this.state.status === "paused") {
      this.update({ status: "running" });
      if (!this.pending) this.schedule();
    }
  }
  stop() {
    this.cancel();
    if (this.state.status === "running" || this.state.status === "paused")
      this.update({ status: "stopped" });
  }
  private cancel() {
    clearTimeout(this.timer);
    this.generation++;
    this.pending = false;
  }
  private schedule(delay = this.state.intervalMs) {
    clearTimeout(this.timer);
    this.timer = setTimeout(() => void this.next(), delay);
  }
  private async next() {
    if (this.state.status !== "running" || this.pending) return;
    const token = this.generation;
    const index = this.state.records.length;
    const request: InspectionRequest = {
      version: 1,
      sample: sequence[index],
      recipe: { ...this.state.recipe },
    };
    const startedAt = new Date().toISOString();
    const start = performance.now();
    this.pending = true;
    try {
      const output = await this.engine(structuredClone(request));
      if (token !== this.generation) return;
      this.pending = false;
      const record: RunRecord = {
        inspectionId: `${this.state.runId}:${index + 1}`,
        sequence: index + 1,
        startedAt,
        completedAt: new Date().toISOString(),
        request,
        ...structuredClone(output),
      };
      this.update({
        records: [...this.state.records, record],
        ...(index + 1 === sequence.length
          ? { status: "completed" as const }
          : {}),
      });
      if (this.state.status === "running")
        this.schedule(
          Math.max(0, this.state.intervalMs - (performance.now() - start)),
        );
    } catch {
      if (token !== this.generation) return;
      this.pending = false;
      this.update({
        status: "error",
        error:
          "검사 실행에 실패했습니다. 완료된 기록을 저장하고 새 배치를 시작하세요.",
      });
    }
  }
}
export function runSummary(records: RunRecord[]) {
  const ok = records.filter((r) => r.result.status === "OK").length;
  return {
    completed: records.length,
    ok,
    ng: records.length - ok,
    passRate: records.length ? (ok / records.length) * 100 : null,
    averageMs: records.length
      ? records.reduce((s, r) => s + r.inspectionMs, 0) / records.length
      : null,
  };
}

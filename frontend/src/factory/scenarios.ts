import fixtures from "../../../backend/src/fs/factory/scenarios.json" with { type: "json" };
export const scenarios = fixtures;
export type Scenario = keyof typeof scenarios;
export type Explanation = {
  scenario: Scenario;
  mode: "ai" | "demo";
  reason: string | null;
  model: string | null;
  evidence: string[];
  narrative: { summary: string; hypotheses: string[]; checks: string[] };
};
export function scenarioEvidence(scenario: Scenario): string[] {
  const data = scenarios[scenario];
  const before = (data.previous.rejected / data.previous.inspected) * 100;
  const after = (data.current.rejected / data.current.inspected) * 100;
  return [
    `직전 10분: 검사 ${data.previous.inspected}개 / 불합격 ${data.previous.rejected}개 / 불합격률 ${before}%`,
    `최근 10분: 검사 ${data.current.inspected}개 / 불합격 ${data.current.rejected}개 / 불합격률 ${after}%`,
    `불합격률 변화: ${after - before >= 0 ? "+" : ""}${after - before}%p`,
    data.event,
  ];
}
export function demoExplanation(
  scenario: Scenario,
  reason: string,
): Explanation {
  const { summary, hypotheses, checks } = scenarios[scenario];
  return {
    scenario,
    mode: "demo",
    reason,
    model: null,
    evidence: scenarioEvidence(scenario),
    narrative: { summary, hypotheses, checks },
  };
}
export function isExplanation(
  value: unknown,
  scenario: Scenario,
): value is Explanation {
  if (!value || typeof value !== "object") return false;
  const data = value as Explanation;
  const texts = (v: unknown): v is string[] =>
    Array.isArray(v) &&
    v.length > 0 &&
    v.length <= 4 &&
    v.every((x) => typeof x === "string" && x.length <= 1000);
  return (
    data.scenario === scenario &&
    ["ai", "demo"].includes(data.mode) &&
    (data.mode !== "ai" || data.model === "gpt-6-astra") &&
    texts(data.evidence) &&
    typeof data.narrative?.summary === "string" &&
    data.narrative.summary.length <= 1000 &&
    texts(data.narrative?.hypotheses) &&
    texts(data.narrative?.checks)
  );
}

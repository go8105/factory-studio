import { parseNC, NC_PROFILE } from "./nc-parser.js";
import { compareProposals } from "./nc-proposals.js";
export async function ncDigest(text) {
  const bytes = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(text),
  );
  return Array.from(new Uint8Array(bytes), (v) =>
    v.toString(16).padStart(2, "0"),
  ).join("");
}
function codeOnly(raw) {
  let comment = false,
    tail = false;
  return raw
    .split("")
    .map((c) => {
      if (tail) return " ";
      if (!comment && c === ";") {
        tail = true;
        return " ";
      }
      if (c === "(") {
        comment = true;
        return " ";
      }
      if (c === ")") {
        comment = false;
        return " ";
      }
      return comment ? " " : c;
    })
    .join("");
}
function ensureProgram(nc) {
  if (!nc.complete || !nc.ended || !nc.segments.length)
    throw Error("완전한 경로와 종료 명령/구분자가 필요합니다");
  for (const block of nc.blocks)
    if (
      block.status === "after-end" &&
      !["", "%"].includes(codeOnly(block.raw).trim())
    )
      throw Error("종료 뒤 실행 코드가 있어 출력할 수 없습니다");
}
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
export function verifyNCOutput(before, after, changes) {
  ensureProgram(after);
  if (
    !same(before.segments, after.segments) ||
    !same(before.finalState, after.finalState)
  )
    throw Error("출력 경로/원호/공구·모달 상태 보존 실패");
  const expected = before.events.map((event) => {
    const change = changes.find((c) => c.line === event.line);
    return change && event.kind === "dwell"
      ? { ...event, seconds: change.toSeconds }
      : event;
  });
  if (
    !same(expected, after.events) ||
    !same(
      before.blocks.map((b) => [
        b.status,
        b.before,
        b.after,
        b.events,
        b.segment,
      ]),
      after.blocks.map((b) => [
        b.status,
        b.before,
        b.after,
        b.events,
        b.segment,
      ]),
    )
  )
    throw Error("출력 블록/비대기 이벤트 보존 실패");
}
export async function generateNCOutput(
  { nc, number = 0, stock, energy, proposalSettings, profile = NC_PROFILE },
  progress = () => {},
) {
  if (
    profile !== NC_PROFILE ||
    nc?.profile !== NC_PROFILE ||
    !Number.isInteger(number) ||
    number < 0
  )
    throw Error("지원 출력 프로필/후보 번호가 아닙니다");
  if (
    typeof nc.originalText !== "string" ||
    (await ncDigest(nc.originalText)) !== nc.sourceHash
  )
    throw Error("원본 해시 불일치 · 다시 해석하세요");
  const before = parseNC(nc.originalText, nc.settings, progress);
  ensureProgram(before);
  if (
    !same(before.segments, nc.segments) ||
    !same(before.events, nc.events) ||
    !same(before.blocks, nc.blocks)
  )
    throw Error("원본 분석 변경 · 다시 해석하세요");
  const changes = [];
  if (number > 0) {
    const report = compareProposals(
      { ...before, sourceHash: nc.sourceHash },
      stock,
      energy,
      proposalSettings,
    );
    const candidate = report.candidates[number - 1];
    if (report.reasons.length || !candidate || candidate.status === "blocked")
      throw Error("현재 품질·공정 조건에서 출력 가능한 후보가 없습니다");
    for (const line of candidate.lines) {
      const r = report.review.find((r) => r.line === line);
      if (!r?.eligible || r.blocked.length)
        throw Error("확인되지 않은 단독 대기 변경");
      changes.push({
        line,
        fromSeconds: r.seconds,
        toSeconds: r.proposedSeconds,
        source: r.source,
      });
    }
  }
  let line = 0;
  const output = nc.originalText.replace(/[^\r\n]+|\r\n|\r|\n/g, (raw) => {
    if (/^[\r\n]+$/.test(raw)) {
      line++;
      return raw;
    }
    const change = changes.find((c) => c.line === line + 1);
    if (!change) return raw;
    const match = /P\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))/i.exec(codeOnly(raw));
    if (!match) throw Error("대기 P 숫자를 보존해 수정할 수 없습니다");
    const value = change.toSeconds.toFixed(9).replace(/\.?0+$/, "") || "0";
    if (Number(value) !== change.toSeconds)
      throw Error("대기 출력 정밀도(소수9자리) 초과");
    const start = match.index + match[0].length - match[1].length;
    return raw.slice(0, start) + value + raw.slice(start + match[1].length);
  });
  const after = parseNC(output, nc.settings, progress);
  verifyNCOutput(before, after, changes);
  return {
    text: output,
    manifest: {
      version: 1,
      post: NC_PROFILE,
      number,
      sourceHash: nc.sourceHash,
      outputHash: await ncDigest(output),
      initialSettings: nc.settings,
      changes,
      moves: after.segments.length,
      events: after.events.length,
      verification: "restricted-parser-roundtrip",
      limitations: [
        "기계 초기 G54 XYZ·기본 모달 상태/공구표 확인 필요",
        "H/D 보정·홀더/지그·실제 장비 검증 없음",
        "실제 LinuxCNC interpreter 검증 아님 · 자동 장비 실행 없음",
      ],
    },
  };
}

import {
  parseControllerNC,
  codeOnly,
  decimal,
  replaceP,
  FANUC_REVIEW_PROFILE,
  stripIncrementalCenter,
} from "./nc-controller.js";
import { NC_PROFILE } from "./nc-parser.js";
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
function hasExecutedCode(block) {
  const code = stripIncrementalCenter(codeOnly(block.raw).trim().toUpperCase());
  return code && code !== "%" && !/^O\d+$/.test(code);
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
  {
    nc,
    number = 0,
    stock,
    energy,
    proposalSettings,
    profile = NC_PROFILE,
    programNumber = 1001,
  },
  progress = () => {},
) {
  if (
    ![NC_PROFILE, FANUC_REVIEW_PROFILE].includes(profile) ||
    ![NC_PROFILE, FANUC_REVIEW_PROFILE].includes(nc?.profile) ||
    !Number.isInteger(number) ||
    number < 0
  )
    throw Error("지원 출력 프로필/후보 번호가 아닙니다");
  if (
    typeof nc.originalText !== "string" ||
    (await ncDigest(nc.originalText)) !== nc.sourceHash
  )
    throw Error("원본 해시 불일치 · 다시 해석하세요");
  const before = parseControllerNC(nc.originalText, nc.settings, progress);
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
  const changedText = nc.originalText
    .split(/(\r\n|\r|\n)/)
    .map((raw, i) => {
      if (i % 2) return raw;
      const change = changes.find((c) => c.line === i / 2 + 1);
      if (!change) return raw;
      return replaceP(
        raw,
        decimal(
          change.toSeconds * (nc.profile === FANUC_REVIEW_PROFILE ? 1000 : 1),
        ),
      );
    })
    .join("");
  let output = changedText;
  let verificationProfile = nc.profile;
  let lineMap = before.blocks.map((b) => b.line);
  let after;
  if (profile === FANUC_REVIEW_PROFILE) {
    if (
      !Number.isInteger(programNumber) ||
      programNumber < 1 ||
      programNumber > 7999
    )
      throw Error("프로그램 번호는1~7999 정수 필요");
    const body = changedText.split(/\r\n|\r|\n/).map((raw, i) => {
      let code = codeOnly(raw).trim().toUpperCase();
      if (code === "%" || /^O\d+$/.test(code)) return "";
      // Incremental I/J is the fixed review profile assumption, not a FANUC G91.1 command.
      code = stripIncrementalCenter(code);
      const dwell = before.events.find(
        (e) => e.line === i + 1 && e.kind === "dwell",
      );
      if (dwell) {
        const seconds =
          changes.find((c) => c.line === i + 1)?.toSeconds ?? dwell.seconds;
        const ms = seconds * 1000;
        if (!Number.isInteger(ms) || ms < 0 || ms > 99999999)
          throw Error(`${i + 1}행 대기 출력은0~99999.999초/밀리초 정밀도 필요`);
        code = replaceP(code, String(ms));
      }
      return code;
    });
    const header = [
      "%",
      "(FANUC REVIEW ONLY - MACHINE NOT CONFIGURED)",
      `O${String(programNumber).padStart(4, "0")}`,
    ];
    output = [...header, ...body, "%"].join("\r\n") + "\r\n";
    lineMap = [
      ...header.map(() => null),
      ...before.blocks.map((b) => b.line),
      null,
      null,
    ];
    verificationProfile = FANUC_REVIEW_PROFILE;
    after = parseControllerNC(
      output,
      { ...nc.settings, profile: verificationProfile },
      progress,
    );
    ensureProgram(after);
    // Compare executed semantics using explicit exported-line -> source-line mapping.
    const remap = (r) => ({ ...r, line: lineMap[r.line - 1] });
    const mapped = {
      ...after,
      segments: after.segments.map(remap),
      events: after.events.map(remap),
    };
    if (
      !same(before.segments, mapped.segments) ||
      !same(before.finalState, after.finalState)
    )
      throw Error("FANUC 출력 경로/모달 상태 보존 실패");
    const expected = before.events.map((e) => {
      const c = changes.find((c) => c.line === e.line);
      return c && e.kind === "dwell" ? { ...e, seconds: c.toSeconds } : e;
    });
    if (!same(expected, mapped.events))
      throw Error("FANUC 출력 이벤트 보존 실패");
    const mappedBlocks = after.blocks.slice(
      header.length,
      header.length + before.blocks.length,
    );
    if (
      !same(
        before.blocks
          .filter((b) => hasExecutedCode(b))
          .map((b) => [b.before, b.after]),
        mappedBlocks
          .filter((b, i) => hasExecutedCode(before.blocks[i]))
          .map((b) => [b.before, b.after]),
      )
    )
      throw Error("FANUC 출력 블록 상태 보존 실패");
  } else {
    if (nc.profile !== NC_PROFILE) throw Error("FANUC→LinuxCNC 변환은 미지원");
    after = parseControllerNC(output, nc.settings, progress);
    verifyNCOutput(before, after, changes);
  }
  return {
    text: output,
    manifest: {
      version: 1,
      post: profile,
      programNumber: profile === FANUC_REVIEW_PROFILE ? programNumber : null,
      verificationProfile,
      lineMap,
      controllerModel: null,
      machineReady: false,
      dwellUnit: profile === FANUC_REVIEW_PROFILE ? "milliseconds" : "seconds",
      notes:
        profile === FANUC_REVIEW_PROFILE
          ? [
              "원본 주석 제외/코드 대문자·CRLF 정규화",
              "G91.1 생략: 증분 I/J 검토 가정",
            ]
          : [],
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
        "실제 컨트롤러 interpreter 검증 아님 · 자동 장비 실행 없음",
      ],
    },
  };
}

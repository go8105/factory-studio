import { parseNC, NC_PROFILE, NC_LIMITS } from "./nc-parser.js";
export const FANUC_REVIEW_PROFILE = "fanuc-mill-review-v1";
export function codeOnly(raw) {
  let comment = false,
    tail = false;
  const masked = raw
    .split("")
    .map((c) => {
      if (tail) return " ";
      if (!comment && c === ";") {
        tail = true;
        return " ";
      }
      if (c === "(") {
        if (comment) throw Error("중첩 주석 미지원");
        comment = true;
        return " ";
      }
      if (c === ")") {
        if (!comment) throw Error("주석 닫기 불일치");
        comment = false;
        return " ";
      }
      return comment ? " " : c;
    })
    .join("");
  if (comment) throw Error("닫히지 않은 주석");
  return masked;
}
export function stripIncrementalCenter(code) {
  return code
    .replace(/G\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))/gi, (word, value) =>
      Number(value) === 91.1 ? "" : word,
    )
    .trim();
}
export function decimal(value) {
  const text = value.toFixed(9).replace(/\.?0+$/, "") || "0";
  if (Number(text) !== value) throw Error("출력 정밀도 소수9자리 초과");
  return text;
}
export function replaceP(raw, value) {
  const match = /P\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))/i.exec(codeOnly(raw));
  if (!match) throw Error("대기 P 숫자를 보존해 수정할 수 없습니다");
  const start = match.index + match[0].length - match[1].length;
  return raw.slice(0, start) + value + raw.slice(start + match[1].length);
}
export function parseControllerNC(text, settings, progress = () => {}) {
  if (settings?.profile !== FANUC_REVIEW_PROFILE)
    return parseNC(text, settings, progress);
  if (
    typeof text !== "string" ||
    new TextEncoder().encode(text).length > NC_LIMITS.bytes
  )
    throw Error("파일 상한2MiB 초과");
  const lines = text.split(/\r\n|\r|\n/);
  if (lines.length > NC_LIMITS.lines) throw Error("원본 행 상한50,000 초과");
  let program = null,
    sawCode = false;
  const normalized = lines.map((raw, i) => {
    const code = codeOnly(raw).trim().toUpperCase();
    if (/^O\d+$/.test(code)) {
      if (
        program !== null ||
        sawCode ||
        !/^O[0-9]{1,4}$/.test(code) ||
        Number(code.slice(1)) < 1 ||
        Number(code.slice(1)) > 7999
      )
        throw Error(`${i + 1}행 프로그램 번호 오류/위치 오류`);
      program = Number(code.slice(1));
      return "";
    }
    if (code && code !== "%") sawCode = true;
    if (stripIncrementalCenter(code) !== code)
      throw Error(`${i + 1}행 FANUC 검토 프로필 G91.1 미지원`);
    const words = code.match(/[A-Z]\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)/g) ?? [];
    if (
      words.some(
        (w) => w.startsWith("G") && Number(w.slice(1).replace(/\s/g, "")) === 4,
      )
    ) {
      const p = /P\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))/.exec(code);
      if (
        !p ||
        !Number.isInteger(Number(p[1])) ||
        Number(p[1]) < 0 ||
        Number(p[1]) > 99999999
      )
        throw Error(`${i + 1}행 G4 P는0~99999999 밀리초 정수 필요`);
      return replaceP(raw, decimal(Number(p[1]) / 1000));
    }
    return raw;
  });
  if (program === null)
    throw Error("FANUC 검토 프로필 O1~O7999 프로그램 번호 필요");
  const result = parseNC(
    normalized.join("\n"),
    { ...settings, profile: NC_PROFILE },
    progress,
  );
  result.blocks.forEach((b, i) => (b.raw = lines[i]));
  result.settings = structuredClone(settings);
  result.profile = FANUC_REVIEW_PROFILE;
  result.programNumber = program;
  result.limitations.push(
    "FANUC 검토용 부분집합 · 실제 장비/컨트롤러 interpreter 미검증 · G4 P 밀리초 가정",
  );
  return result;
}

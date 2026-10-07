// One command per completed gesture; native text editing keeps its own history.
export function shortcutCommand(event) {
  if (
    event.isComposing ||
    event.keyCode === 229 ||
    event.repeat ||
    event.altKey
  )
    return null;
  const key = event.key.toLowerCase();
  if (key === "escape") return "cancel";
  const modifier = event.ctrlKey || event.metaKey;
  if (modifier && key === "s") return "save";
  const target = event.composedPath?.()[0] ?? event.target;
  if (
    target?.closest?.(
      'input, textarea, select, [contenteditable]:not([contenteditable="false"])',
    )
  )
    return null;
  if (modifier) {
    if (key === "z") return event.shiftKey ? "redo" : "undo";
    if (key === "y" && event.ctrlKey) return "redo";
    return null;
  }
  if (key === "delete") return "delete";
  if (key === "backspace") return "undo-point";
  if (key === "f") return "fit";
  if (key === "?") return "help";
  return null;
}
export class DraftHistory {
  constructor(limit = 50) {
    this.limit = limit;
    this.clear();
  }
  clear() {
    this.past = [];
    this.future = [];
    this.group = null;
  }
  endGroup() {
    this.group = null;
  }
  get active() {
    return this.past.length > 0 || this.future.length > 0;
  }
  get canUndo() {
    return this.past.length > 0;
  }
  get canRedo() {
    return this.future.length > 0;
  }
  record(before, after, group = null) {
    if (JSON.stringify(before) === JSON.stringify(after)) return false;
    if (!group || this.group !== group) this.past.push(structuredClone(before));
    if (this.past.length > this.limit) this.past.shift();
    this.group = group;
    this.future = [];
    return true;
  }
  undo(current) {
    if (!this.canUndo) return null;
    this.future.push(structuredClone(current));
    this.endGroup();
    return this.past.pop();
  }
  redo(current) {
    if (!this.canRedo) return null;
    this.past.push(structuredClone(current));
    this.endGroup();
    return this.future.pop();
  }
}
export function dependentFeatures(operations, id) {
  const affected = new Set([id]),
    result = [];
  for (const f of operations) {
    if (f.id === id) continue;
    if (affected.has(f.referenceId) || affected.has(f.sourceId)) {
      affected.add(f.id);
      result.push(f);
    }
  }
  return result;
}
export const SHORTCUT_HELP =
  "Ctrl/⌘+Z 실행 취소 · Ctrl/⌘+Shift+Z / Ctrl+Y 다시 실행 · Esc 조작/계산 취소 · Delete 선택 삭제 · F 전체 보기 · Ctrl/⌘+S 확정 설계 저장 · ? 도움말. 입력칸의 실행 취소는 글자/숫자 편집에 적용됩니다.";

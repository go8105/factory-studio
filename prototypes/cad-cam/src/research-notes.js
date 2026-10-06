export function validateNotes(value) {
  if (!Array.isArray(value) || value.length > 200)
    throw Error("최대 200개 기록만 보관할 수 있습니다.");
  const ids = new Set();
  for (const note of value) {
    if (
      !note ||
      typeof note.revision !== "string" ||
      !/^POC-\d{2,4}$/.test(note.revision)
    )
      throw Error("기준 설계가 올바르지 않습니다.");
    for (const key of [
      "id",
      "createdAt",
      "title",
      "hypothesis",
      "result",
      "decision",
    ]) {
      const max =
        key === "title" ? 120 : ["id", "createdAt"].includes(key) ? 80 : 4000;
      if (
        typeof note[key] !== "string" ||
        !note[key].trim() ||
        note[key].length > max
      )
        throw Error("연구 기록의 필수 값 또는 길이를 확인하세요.");
    }
    if (ids.has(note.id) || !Number.isFinite(Date.parse(note.createdAt)))
      throw Error("중복 ID 또는 올바르지 않은 날짜입니다.");
    for (const [field, max] of [
      ["designFolder", 500],
      ["designFile", 150],
    ]) {
      if (
        note[field] !== undefined &&
        (typeof note[field] !== "string" ||
          note[field].length > max ||
          note[field].includes("\0"))
      )
        throw Error("설계 폴더/파일명을 확인하세요.");
    }
    ids.add(note.id);
  }
  return value.map(
    ({
      id,
      createdAt,
      revision,
      title,
      hypothesis,
      result,
      decision,
      designFolder = "",
      designFile = "",
    }) => ({
      id,
      createdAt,
      revision,
      title,
      hypothesis,
      result,
      decision,
      designFolder,
      designFile,
    }),
  );
}
export function mergeNotes(current, incoming) {
  const map = new Map(validateNotes(current).map((n) => [n.id, n]));
  for (const n of validateNotes(incoming)) {
    if (map.has(n.id) && JSON.stringify(map.get(n.id)) !== JSON.stringify(n))
      throw Error("같은 ID의 내용이 다릅니다. 원본 기록을 보존했습니다.");
    map.set(n.id, n);
  }
  return validateNotes([...map.values()]);
}

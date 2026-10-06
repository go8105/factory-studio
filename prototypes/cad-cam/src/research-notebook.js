import "./research-notebook.css";
import { validateNotes, mergeNotes } from "./research-notes.js";
const $ = (s) => document.querySelector(s);
const base = import.meta.env.BASE_URL;
const scope = new URLSearchParams(location.search).get("scope") || "local";
$("#back").href =
  `${base}soap-poc.html?embedded=1&scope=${encodeURIComponent(scope)}&poc=1`;
const key = `factory-soap-research:v1:${scope}`;
let notes = [],
  history = null;
const node = (tag, text) => {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  return el;
};
function renderNotes() {
  $("#notes").replaceChildren();
  for (const n of notes.toReversed()) {
    const card = node("article");
    card.append(
      node(
        "small",
        `${n.revision} · ${new Date(n.createdAt).toLocaleString("ko-KR")}`,
      ),
      node("h3", n.title),
    );
    for (const [label, k] of [
      ["가설·조건", "hypothesis"],
      ["관찰·측정", "result"],
      ["판단·다음 설계", "decision"],
    ])
      card.append(node("h3", label), node("p", n[k]));
    if (n.designFolder || n.designFile)
      card.append(
        node("h3", "설계 파일 참조"),
        node(
          "p",
          `${n.designFolder}
${n.designFile}`,
        ),
      );
    $("#notes").append(card);
  }
}
function persist(value) {
  const valid = validateNotes(value);
  localStorage.setItem(key, JSON.stringify(valid));
  notes = valid;
  renderNotes();
}
try {
  notes = validateNotes(JSON.parse(localStorage.getItem(key) || "[]"));
  renderNotes();
} catch {
  $("#saveStatus").textContent =
    "저장 기록을 읽지 못했습니다. 기존 저장값은 유지합니다. 백업을 확인하세요.";
}
try {
  const response = await fetch(`${base}soap-poc/research-history.json`, {
    cache: "no-store",
  });
  if (!response.ok)
    throw Error("설계 이력을 불러오지 못했습니다. 관리자 세션을 확인하세요.");
  history = await response.json();
  $("#notice").textContent = history.notice;
  for (const entry of history.entries) {
    const card = node("article");
    card.id = entry.id;
    card.append(
      node("small", `${entry.id} · ${entry.date} · 디지털 설계`),
      node("h2", entry.title),
    );
    const dl = node("dl");
    dl.append(
      node("dt", "설계 폴더"),
      node("dd", "prototypes/cad-cam/private/soap-poc/"),
    );
    for (const [label, k] of [
      ["설계 이유", "reason"],
      ["주요 가정", "dimensions"],
      ["검증 결과", "result"],
      ["남은 문제", "limits"],
      ["다음 방향", "next"],
    ])
      dl.append(node("dt", label), node("dd", entry[k]));
    card.append(dl);
    const details = node("details");
    details.append(
      node("summary", `설계 파일 ${entry.files.length}개 · 다운로드 / SHA-256`),
    );
    const list = node("ul");
    for (const file of entry.files) {
      const li = node("li"),
        a = node("a", file.name);
      a.href = `${base}soap-poc/${encodeURIComponent(file.name)}`;
      a.download = file.name;
      li.append(a, node("br"), node("code", file.sha256));
      list.append(li);
    }
    details.append(list);
    card.append(details);
    $("#history").append(card);
  }
} catch (e) {
  $("#notice").textContent = e.message;
}
$("#noteForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget));
  try {
    persist([
      ...notes,
      {
        id: crypto.randomUUID(),
        createdAt: new Date().toISOString(),
        ...values,
      },
    ]);
    event.currentTarget.reset();
    $("#saveStatus").textContent =
      "이 브라우저에 저장했습니다. JSON 백업을 내려받아 보관하세요.";
  } catch (e) {
    $("#saveStatus").textContent = `저장하지 못했습니다: ${e.message}`;
  }
});
$("#export").addEventListener("click", () => {
  const blob = new Blob(
    [
      JSON.stringify(
        {
          schemaVersion: 1,
          exportedAt: new Date().toISOString(),
          history,
          notes,
        },
        null,
        2,
      ),
    ],
    { type: "application/json" },
  );
  const url = URL.createObjectURL(blob),
    a = node("a");
  a.href = url;
  a.download = "soap-research-notebook.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
$("#import").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    if (file.size > 4_000_000)
      throw Error("4MB 이하 JSON만 불러올 수 있습니다.");
    const data = JSON.parse(await file.text());
    if (data.schemaVersion !== 1) throw Error("지원하지 않는 백업 버전입니다.");
    persist(mergeNotes(notes, data.notes));
    $("#saveStatus").textContent =
      "백업의 연구 기록을 추가했습니다. 기존 설계 이력은 유지합니다.";
  } catch (e) {
    $("#saveStatus").textContent = `불러오지 못했습니다: ${e.message}`;
  }
  event.target.value = "";
});

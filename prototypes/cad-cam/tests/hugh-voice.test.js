import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { createHughVoice } from "../src/hugh-voice.js";
test("recognition adapter handles final-only wake/commands, echo suppression, errors and cleanup", () => {
  const dom = new JSDOM('<div class="workspace"></div>', {
    url: "http://localhost",
    pretendToBeVisual: true,
  });
  globalThis.document = dom.window.document;
  let instances = [],
    calls = [],
    spoken = [];
  class Recognition {
    constructor() {
      instances.push(this);
    }
    start() {
      this.onstart?.();
    }
    abort() {
      this.onend?.();
    }
    emit(text, final = true) {
      this.onresult({
        resultIndex: 0,
        results: [Object.assign([{ transcript: text }], { isFinal: final })],
      });
    }
  }
  const host = {
    SpeechRecognition: Recognition,
    SpeechSynthesisUtterance: class {
      constructor(text) {
        this.text = text;
      }
    },
    speechSynthesis: {
      cancel() {},
      speak(u) {
        spoken.push(u);
      },
    },
    addEventListener() {},
  };
  const controller = createHughVoice(
    {
      propose: () => {
        calls.push("propose");
        return "후보 3개";
      },
      play: (n) => {
        calls.push(n);
        return "재생";
      },
      stop: () => calls.push("stop"),
    },
    host,
  );
  document.getElementById("hugh-enable").click();
  let r = instances[0];
  assert.equal(r.lang, "ko-KR");
  r.emit("헤이 휴디", false);
  assert.equal(spoken.length, 0);
  r.emit("헤이 휴디 최적안 제안해줘");
  assert.deepEqual(calls, ["propose"]);
  assert.equal(spoken.length, 1);
  r.emit("2번 실행");
  assert.deepEqual(calls, ["propose"]); // detached recognition cannot trigger itself via TTS
  controller.off();
  assert.equal(document.getElementById("hugh-disable").disabled, true);
  document.getElementById("hugh-enable").click();
  r = instances.at(-1);
  r.onerror({ error: "not-allowed" });
  assert.match(
    document.getElementById("hugh-reply").textContent,
    /권한이 거절/,
  );
  assert.equal(document.getElementById("hugh-enable").disabled, false);
  document.querySelector("#hugh-text").value = "두 번째 시뮬레이션 실행해줘";
  document
    .querySelector("#hugh-form")
    .dispatchEvent(new dom.window.Event("submit", { cancelable: true }));
  assert.equal(calls.at(-1), 2);
  assert.match(document.getElementById("hugh-reply").textContent, /텍스트/);
  controller.off();
  dom.window.close();
  delete globalThis.document;
});
test("unsupported browser provides buttons without starting recognition", () => {
  const dom = new JSDOM('<div class="workspace"></div>');
  globalThis.document = dom.window.document;
  const c = createHughVoice(
    { propose: () => "입력 필요", play: () => "", stop() {} },
    { addEventListener() {} },
  );
  assert.equal(document.getElementById("hugh-enable").disabled, true);
  assert.match(document.getElementById("hugh-state").textContent, /미지원/);
  document.getElementById("hugh-propose").click();
  assert.match(document.getElementById("hugh-reply").textContent, /입력 필요/);
  c.off();
  dom.window.close();
  delete globalThis.document;
});

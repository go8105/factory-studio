import { HughCommands } from "./hugh-commands.js";
export function createHughVoice(actions, host = window) {
  const panel = document.createElement("section");
  panel.className = "hugh-panel";
  panel.innerHTML = `<div class="hugh-heading"><strong>Hugh-D · 휴디</strong><span id="hugh-state" role="status">음성 꺼짐</span></div><p>마이크를 켜고 “헤이 휴디” → “최적안 제안해줘” → “2번 시뮬레이션 실행해줘”. 호출 후 30초 동안 명령을 듣습니다.</p><p class="muted">Chrome 한국어 인식은 브라우저 서비스로 원격 처리될 수 있습니다. 인식 문장은 저장하지 않습니다. 열린 화면에서만 대기합니다.</p><div class="buttons"><button id="hugh-enable">음성 켜기 · 마이크 허용</button><button id="hugh-disable" disabled>마이크 끄기</button><button id="hugh-propose">NC 에너지 제안</button><button id="hugh-stop">시뮬레이션 정지</button></div><p id="hugh-reply" aria-live="polite">NC·소재·시간/소비·품질 검토를 먼저 준비하세요.</p><details><summary>텍스트 명령 테스트 (실제 음성 아님)</summary><form id="hugh-form"><label>테스트 명령<input id="hugh-text" autocomplete="off" placeholder="2번 시뮬레이션 실행해줘"></label><button>명령 테스트</button></form></details>`;
  document.querySelector(".workspace").prepend(panel);
  const $ = (id) => panel.querySelector("#" + id);
  const Recognition = host.SpeechRecognition || host.webkitSpeechRecognition;
  let enabled = false,
    recognition = null,
    speaking = false,
    session = 0,
    retry = null,
    speechTimer = null,
    utterance = null,
    manualIndex = 0,
    endedCount = 0;
  const state = (text) => {
    $("hugh-state").textContent = text;
    panel.dataset.listening = String(enabled);
  };
  function off() {
    enabled = false;
    clearTimeout(retry);
    clearTimeout(speechTimer);
    commands.reset();
    recognition?.abort();
    recognition = null;
    host.speechSynthesis?.cancel();
    speaking = false;
    utterance = null;
    $("hugh-enable").disabled = !Recognition;
    $("hugh-disable").disabled = true;
    state("음성 꺼짐");
  }
  const commands = new HughCommands({ ...actions, off });
  function listen() {
    if (!enabled || speaking || recognition || document.hidden) return;
    const r = new Recognition(),
      own = ++session;
    recognition = r;
    r.lang = "ko-KR";
    r.continuous = true;
    r.interimResults = false;
    r.onstart = () => {
      if (recognition === r && enabled)
        state(
          Date.now() < commands.until
            ? "명령 대기 · 30초"
            : "호출 대기 · 헤이 휴디",
        );
    };
    r.onresult = (event) => {
      if (recognition !== r || !enabled || speaking) return;
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (recognition !== r || speaking) break;
        if (event.results[i].isFinal) {
          endedCount = 0;
          dispatch(event.results[i][0].transcript, `${own}:${i}`, false);
        }
      }
    };
    r.onerror = (event) => {
      if (recognition !== r) return;
      if (event.error === "no-speech") {
        state("호출 대기 · 음성 없음");
        return;
      }
      off();
      $("hugh-reply").textContent =
        {
          "not-allowed":
            "마이크 권한이 거절되었습니다. Chrome·macOS 마이크 권한을 확인하세요.",
          "audio-capture": "사용 가능한 마이크가 없습니다.",
          network:
            "음성 인식 서비스에 연결하지 못했습니다. 네트워크를 확인하고 다시 켜세요.",
        }[event.error] ||
        `음성 인식 종료: ${event.error}. 다시 켜거나 버튼을 사용하세요.`;
    };
    r.onend = () => {
      if (recognition !== r) return;
      recognition = null;
      if (enabled && !speaking) {
        if (++endedCount >= 5) {
          off();
          $("hugh-reply").textContent =
            "음성 서비스가 반복 종료되었습니다. 음성을 다시 켜거나 버튼을 사용하세요.";
        } else retry = setTimeout(listen, 700);
      }
    };
    try {
      r.start();
    } catch (e) {
      off();
      $("hugh-reply").textContent = `음성 시작 실패: ${e.message}`;
    }
  }
  function reply(text, audio) {
    $("hugh-reply").textContent = text;
    if (
      !audio ||
      !enabled ||
      !host.speechSynthesis ||
      !host.SpeechSynthesisUtterance
    )
      return;
    speaking = true;
    recognition?.abort();
    recognition = null;
    clearTimeout(retry);
    host.speechSynthesis.cancel();
    state("휴디 응답 중");
    utterance = new host.SpeechSynthesisUtterance(text);
    utterance.lang = "ko-KR";
    const finish = () => {
      if (!speaking) return;
      clearTimeout(speechTimer);
      speaking = false;
      utterance = null;
      if (enabled) {
        commands.until = Date.now() + 30000;
        retry = setTimeout(listen, 500);
      }
    };
    utterance.onend = finish;
    utterance.onerror = finish;
    // Do not reopen recognition while a stalled synthesis engine is still talking.
    speechTimer = setTimeout(() => {
      host.speechSynthesis.cancel();
      finish();
    }, 45000);
    host.speechSynthesis.speak(utterance);
  }
  function dispatch(text, key, manual) {
    try {
      const response = commands.accept(text, key, manual);
      if (response)
        reply((manual ? "텍스트/버튼 테스트 · " : "") + response, !manual);
    } catch (e) {
      reply(e.message, !manual);
    }
  }
  $("hugh-enable").onclick = () => {
    if (!Recognition) return;
    enabled = true;
    endedCount = 0;
    commands.reset();
    $("hugh-enable").disabled = true;
    $("hugh-disable").disabled = false;
    state("마이크 시작 중");
    listen();
  };
  $("hugh-disable").onclick = off;
  $("hugh-propose").onclick = () =>
    dispatch("최적안 제안해줘", `button:${++manualIndex}`, true);
  $("hugh-stop").onclick = () =>
    dispatch("멈춰", `button:${++manualIndex}`, true);
  $("hugh-form").onsubmit = (e) => {
    e.preventDefault();
    dispatch($("hugh-text").value, `manual:${++manualIndex}`, true);
    $("hugh-text").value = "";
  };
  if (!Recognition) {
    $("hugh-enable").disabled = true;
    state("브라우저 음성 인식 미지원 · 버튼 사용");
  }
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      off();
      actions.stop();
    }
  });
  host.addEventListener("pagehide", () => {
    off();
    actions.stop();
  });
  return { off };
}

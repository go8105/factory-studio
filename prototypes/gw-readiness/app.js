/* GW-READY-01 검토용 UI. 네트워크·인증·DB·영구 저장을 사용하지 않는다. */
(() => {
  "use strict";
  const main = document.querySelector("#main"),
    nav = document.querySelector("#navigation"),
    dialog = document.querySelector("#dialog"),
    role = document.querySelector("#role");
  const state = {
    draft: false,
    mfaScene: false,
    codesSaved: false,
    policy: {
      interval: "30",
      rpo: "60",
      rto: "240",
      docs: "36",
      audit: "12",
      backup: "30",
    },
    menu: false,
  };
  let opener = null,
    dirty = false,
    discarding = false,
    originalDialog = null;
  const screens = [
    ["home", "내 업무"],
    ["setup", "회사 시작 안내"],
    ["people", "직원 연결"],
    ["security", "내 계정 보안"],
    ["operations", "운영 준비"],
    ["policy", "보관·복구 기준"],
    ["backup", "백업·복구 기록"],
    ["retention", "보관 검토"],
  ];
  const adminOnly = new Set([
    "setup",
    "people",
    "operations",
    "policy",
    "backup",
    "retention",
  ]);
  const escape = (s) =>
    String(s).replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  const button = (text, action, primary = false) =>
    `<button type="button" ${primary ? 'class="primary"' : ""} data-action="${action}">${text}</button>`;
  const heading = (title, desc) =>
    `<div class="toolbar"><div><p class="eyebrow">새 회사 · 운영팀</p><h1>${title}</h1></div><a href="#help" class="help">? 사용 안내</a></div><p class="subtitle">${desc}</p>`;
  function notice(message) {
    document.querySelector("#status").textContent = message;
  }
  function open(title, body) {
    opener = document.activeElement;
    document.querySelector("#dialog-title").textContent = title;
    document.querySelector("#dialog-body").innerHTML = body;
    dirty = false;
    discarding = false;
    dialog.showModal();
  }
  function close() {
    dialog.close();
    dirty = false;
    discarding = false;
    opener?.focus();
  }
  function askClose() {
    if (!dirty) {
      close();
      return;
    }
    if (discarding) {
      resume();
      return;
    }
    originalDialog = {
      title: document.querySelector("#dialog-title").textContent,
      body: document.querySelector("#dialog-body").innerHTML,
      values: [...dialog.querySelectorAll("input")].map((i) => [
        i.name,
        i.value,
        i.checked,
      ]),
    };
    discarding = true;
    document.querySelector("#dialog-title").textContent =
      "입력을 저장하지 않고 닫을까요?";
    document.querySelector("#dialog-body").innerHTML =
      `<p>입력한 내용은 아직 저장하지 않았습니다.</p><div class="actions">${button("계속 편집", "resume", true)}${button("변경 버리기", "discard")}</div>`;
    dialog.querySelector("button[data-action=resume]").focus();
  }
  function resume() {
    document.querySelector("#dialog-title").textContent = originalDialog.title;
    document.querySelector("#dialog-body").innerHTML = originalDialog.body;
    for (const [name, value, checked] of originalDialog.values) {
      const input = [...dialog.querySelectorAll("input")].find(
        (i) => i.name === name,
      );
      if (input) {
        input.value = value;
        input.checked = checked;
      }
    }
    discarding = false;
    document
      .querySelector("#dialog-body")
      .querySelector("input,select,button")
      ?.focus();
  }
  function error(form, message, id) {
    form.querySelector(".error-summary").textContent = message;
    const input = form.querySelector("#" + id);
    input.setAttribute("aria-invalid", "true");
    form.querySelector("#" + id + "-error").textContent = message;
    input.focus();
  }
  function render() {
    notice("");
    const route = location.hash.slice(1) || "home";
    nav.innerHTML = screens
      .filter(([id]) => role.value === "admin" || !adminOnly.has(id))
      .map(
        ([id, label]) =>
          `<a href="#${id}" ${route === id ? 'aria-current="page"' : ""}>${label}</a>`,
      )
      .join("");
    if (role.value === "staff" && adminOnly.has(route)) {
      main.innerHTML =
        heading(
          "관리자에게 요청하세요",
          "이 화면은 회사 운영 담당자가 사용합니다.",
        ) +
        `<section class="card"><p>직원 계정에서는 운영 정책과 다른 사람의 보안 설정을 바꾸지 않습니다.</p><a href="#home">내 업무로 이동</a></section>`;
      return;
    }
    const views = {
      home: () =>
        heading(
          "내 업무",
          "오늘 내가 처리할 일부터 확인하세요. 회사 자료는 각자의 로그인과 현재 권한으로 처리합니다.",
        ) +
        `<section class="notice">설계 시안의 합성 업무입니다. 아래 버튼은 실제 기안·승인을 실행하지 않습니다.</section><div class="grid"><section class="card"><h2>내가 결재할 문서 <span class="badge neutral">2건</span></h2><div class="task"><p class="muted">일반 기안 · 오늘까지</p><h3>공구 구매 검토</h3><p>요청 내용과 금액을 확인한 뒤 처리하세요.</p>${button("문서 검토", "review-doc", true)}</div><div class="task"><p class="muted">일반 기안</p><h3>다음 주 생산 일정 공유</h3>${button("문서 검토", "review-doc")}</div></section><section class="card"><h2>자주 하는 업무</h2><p>제목·설명·결재선을 확인하고 초안으로 시작합니다.</p>${button("새 기안", "draft", true)}<hr><h3>내 계정 보안</h3><p>인증 앱과 백업 코드를 준비해 두면 휴대폰을 바꿀 때 복구할 수 있습니다.</p><a href="#security">내 계정 보안 열기</a></section><section class="card wide"><h2>함께 일하기</h2><div class="row"><div><strong>팀 공지</strong><small>회사 전체 공지 1건</small></div>${button("공지 확인", "demo-work")}</div><div class="row"><div><strong>내 일정</strong><small>오후 2시 · 작업 계획 회의</small></div>${button("참석 확인", "demo-work")}</div><div class="row"><div><strong>업무 대화</strong><small>운영팀 · 새 메시지 3건</small></div>${button("대화 열기", "demo-work")}</div></section></div>`,
      setup: () =>
        heading(
          "회사 시작 안내",
          "관리자 1명과 직원 9명이 순서대로 준비합니다. 직원 수는 이번 준비 기준이며 제품의 최대 인원 제한이 아닙니다.",
        ) +
        `<section class="card"><h2>처음 준비할 일</h2><ol class="steps">${[
          [
            "회사·부서 확인",
            "회사 1개 · 운영팀 1개. 기존 회사·HR 정보를 다시 만들지 않습니다.",
            "people",
            "직원 목록 보기",
          ],
          [
            "계정과 본인 연결",
            "직원 9명은 자기 로그인으로 사번과 이름을 확인해 동의합니다.",
            "people",
            "연결 준비 보기",
          ],
          [
            "인증 앱과 백업 코드",
            "관리자부터 등록하고 직원들이 각자 준비합니다.",
            "security",
            "내 보안 설정",
          ],
          [
            "백업과 복구 기준",
            "초기값을 검토한 뒤 회사 기준으로 저장합니다.",
            "policy",
            "기준 검토",
          ],
          [
            "시범 업무 확인",
            "2개 계정의 기안·결재와 권한 회수, 복구 시험 결과를 확인합니다.",
            "operations",
            "운영 준비 보기",
          ],
        ]
          .map(
            (s, i) =>
              `<li><span class="step-number">${i + 1}</span><div class="step-body"><h3>${s[0]}</h3><p class="muted">${s[1]}</p><a href="#${s[2]}">${s[3]}</a></div></li>`,
          )
          .join("")}</ol></section>`,
      people: () =>
        heading(
          "직원 연결",
          "회사 계정·HR 직원·GW 사용 연결은 각각 확인합니다. 관리자가 다른 직원을 대신해 본인 동의하지 않습니다.",
        ) +
        `<section class="notice">합성 구성 10명입니다. 실제 계정은 이 시제품에서 생성하지 않습니다.</section><section class="card"><h2>연결 상태</h2>${Array.from({ length: 10 }, (_, n) => `<div class="row"><div><strong>${n === 0 ? "초기 관리자" : `직원 ${String(n).padStart(2, "0")}`}</strong><small>SYN-${String(n + 1).padStart(3, "0")} · 운영팀 · ${n === 0 ? "운영 관리 역할 겸임" : "관리 역할 없음"}</small></div><div><span class="badge ${n > 7 ? "pending" : ""}">${n > 7 ? "본인 확인 대기" : "연결 완료"}</span> ${button(n > 7 ? "연결 안내 보기" : "허용 범위 보기", n > 7 ? "invite" : "scope")}</div></div>`).join("")}</section>`,
      security: () =>
        heading(
          "내 계정 보안",
          "비밀번호 확인 → 인증 앱 등록 → 백업 코드 보관 순서로 준비합니다. 다른 사람의 인증 비밀과 코드는 조회하지 않습니다.",
        ) +
        `<div class="grid"><section class="card"><h2>인증 앱 <span class="badge ${state.mfaScene ? "neutral" : "pending"}">${state.mfaScene ? "등록 완료 장면" : "등록 전 장면"}</span></h2><p>로그인할 때 비밀번호와 인증 앱의 6자리 번호를 확인합니다.</p>${button("인증 앱 등록 흐름 보기", "enroll", true)}<details><summary>인증 앱이 무엇인가요?</summary><p>휴대폰의 호환 인증 앱에서 짧은 주기로 바뀌는 번호를 보여 줍니다. 실제 제품에서는 QR 또는 설정 키로 등록합니다.</p></details></section><section class="card"><h2>백업 코드</h2><p>휴대폰을 사용할 수 없을 때 한 번씩 사용하는 복구 수단입니다. 다시 발급하면 이전 코드는 모두 무효가 됩니다.</p>${button("백업 코드 보관 흐름 보기", "codes")}<div class="actions"><a href="#recovery">휴대폰을 잃어버렸나요?</a></div></section><section class="card wide"><h2>최근 보안 기록</h2><p class="muted">합성 예시 · 비밀번호·인증 번호·문서 본문은 기록하지 않습니다.</p><div class="row"><span>오늘 09:00 · 로그인</span><span class="badge">본인 계정</span></div><div class="row"><span>지난주 · 백업 코드 새 발급</span><span class="badge neutral">이전 코드 무효</span></div></section></div>`,
      operations: () =>
        heading(
          "운영 준비",
          "남은 조건과 다음 행동을 함께 표시합니다. 화면의 체크만으로 인증·백업이 완료되지는 않습니다.",
        ) +
        `<section class="notice warn"><strong>아직 실제 운영을 시작할 수 없습니다.</strong><br>이 시제품에는 실제 인증·백업·인수 증거가 없습니다. 아래 상태는 검토용 예시입니다.</section><div class="meta"><div><span class="muted">직원 연결</span><p class="number">8 / 10명</p><span class="badge pending">2명 본인 동의 필요</span></div><div><span class="muted">인증 앱 준비</span><p class="number">6 / 10명</p><span class="badge pending">4명 등록 필요</span></div><div><span class="muted">복원 시험</span><p class="number">확인 필요</p><span class="muted">검증된 실행 기록 필요</span></div></div><section class="card"><h2>남은 일</h2>${[
          [
            "직원 2명의 본인 동의",
            "연결 요청을 받은 직원이 직접 확인합니다.",
            "people",
            "직원 연결",
          ],
          [
            "계정 보안과 복구 준비",
            "인증 앱 등록·백업 코드 보관을 각자 마칩니다.",
            "security",
            "내 계정 보안",
          ],
          [
            "회사 보관·복구 기준 확인",
            "초기값을 검토하고 담당자와 사유를 남깁니다.",
            "policy",
            "기준 검토",
          ],
          [
            "백업 복원 시험과 담당자 확인",
            "서명 검증된 실행 결과와 권한 회수 재적용 결과가 필요합니다.",
            "backup",
            "복구 기록 확인",
          ],
        ]
          .map(
            (x) =>
              `<div class="row"><div><strong>${x[0]}</strong><small>${x[1]}</small></div><a href="#${x[2]}">${x[3]}</a></div>`,
          )
          .join(
            "",
          )}<div class="actions">${button("시범 전환 조건 보기", "pilot", true)}</div></section>`,
      policy: () =>
        heading(
          "보관·복구 기준",
          "처음 제시하는 운영 기본안입니다. 회사 업무와 용량에 맞게 검토한 뒤 새 버전으로 저장합니다.",
        ) +
        `<section class="notice">초기안: 일반 업무문서 3년·보안 기록 1년·백업 30일, 백업 간격 30분·허용 손실 60분·복구 목표 4시간. 법정 기간이나 실제 성능 보장이 아닙니다.</section><section class="card"><h2>검토 중인 기준 <span class="badge neutral">초안</span></h2><div class="row"><span>문서 보관</span><strong>${escape(state.policy.docs)}개월 · 만료 시 담당자 검토</strong></div><div class="row"><span>보안 기록 보관</span><strong>${escape(state.policy.audit)}개월</strong></div><div class="row"><span>백업 보관</span><strong>${escape(state.policy.backup)}일</strong></div><div class="row"><span>백업 간격</span><strong>${escape(state.policy.interval)}분</strong></div><div class="row"><span>허용 데이터 손실 / 복구 목표</span><strong>${escape(state.policy.rpo)}분 / ${escape(state.policy.rto)}분</strong></div><p class="muted">원본 기록은 자동 삭제하지 않습니다. 이전 확정 버전은 보존하고 다음 버전을 만듭니다.</p>${button("기준 검토·수정", "policy-edit", true)}${state.draft ? '<p class="muted">시제품 내 검토값이 변경되었습니다. 서버에는 저장하지 않았습니다.</p>' : ""}</section>`,
      backup: () =>
        heading(
          "백업·복구 기록",
          "백업을 만들었다는 기록과 새 환경에서 복원까지 확인한 기록을 구분합니다.",
        ) +
        `<section class="notice warn">검토용 예시입니다. 실제 실행 결과·외부 저장소·키·복원 환경은 연결하지 않았습니다.</section><div class="grid"><section class="card"><h2>백업</h2><p><span class="badge neutral">예시 실행 기록</span></p><div class="row"><span>실행 시각</span><strong>오늘 09:00</strong></div><div class="row"><span>암호화 / 저장 위치</span><strong>확인 필요</strong></div><p class="muted">백업 비밀·저장소 비밀번호는 화면에 표시하지 않습니다.</p>${button("기록의 확인 항목 보기", "backup-info")}</section><section class="card"><h2>복원 시험</h2><p>다른 DB에 복원하고 자료·세션·회수 권한까지 비교해야 합니다.</p><ol><li>원장과 기록 지문 대조</li><li>이전 세션 무효화</li><li>백업 이후 정지·권한 회수 재적용</li><li>새 로그인으로 업무와 접근 거부 확인</li></ol>${button("복원 결과 화면 보기", "restore", true)}</section></div>`,
      retention: () =>
        heading(
          "보관 검토",
          "검토 기한에 도달한 기록을 확인합니다. 보안 관리자라는 이유만으로 비공개 문서의 제목·본문을 열지 않습니다.",
        ) +
        `<section class="notice">기한 도달은 자동 삭제가 아닙니다. 보존 중지 요청이 있으면 반출·삭제 흐름을 멈추고 담당자가 확인합니다.</section><section class="card"><h2>검토할 기록</h2><div class="row"><div><strong>허용된 일반 기안 · GW-000021</strong><small>보관 검토 기한 도달 · 본인 열람 허용</small></div>${button("검토 절차 보기", "retention-review")}</div><div class="row"><div><strong>비공개 기록 · 식별 번호만 표시</strong><small>본문 열람 권한 없음 · 담당자 검토 필요</small></div><span class="badge pending">원문 열람 불가</span></div><div class="row"><div><strong>보존 중지 대상 · GW-000008</strong><small>분쟁·감사 등 회사 확인 필요 · 임의 해제하지 않음</small></div><span class="badge neutral">처리 보류</span></div></section>`,
      recovery: () =>
        heading(
          "계정 복구",
          "휴대폰 변경·인증 수단 분실·관리자 계정 분실을 서로 구분합니다.",
        ) +
        `<section class="card compact"><h2>어떤 상황인가요?</h2><div class="row"><div><strong>비밀번호와 백업 코드가 있어요</strong><small>코드를 한 번 사용한 뒤 인증 앱을 다시 등록합니다.</small></div>${button("복구 단계 보기", "recover")}</div><div class="row"><div><strong>백업 코드도 없어요</strong><small>회사 복구 담당자에게 본인 확인을 요청합니다. 일반 직원이나 총 관리자가 대신 로그인하지 않습니다.</small></div>${button("복구 요청 절차", "assisted")}</div><div class="row"><div><strong>유일한 관리자가 계정을 잃었어요</strong><small>미리 보관한 긴급 복구 수단과 서버 운영 절차가 필요합니다.</small></div>${button("관리자 복구 준비", "emergency")}</div></section>`,
      help: () =>
        heading(
          "이 화면 사용 안내",
          "화면에서 해야 할 행동과 결과를 먼저 설명합니다. 학습 진도·시험·채점 기능은 만들지 않습니다.",
        ) +
        `<section class="card"><h2>처음 사용하는 직원</h2><ol><li>자기 계정으로 로그인하고 본인 연결을 확인합니다.</li><li>인증 앱과 백업 코드를 준비합니다.</li><li>내 업무에서 지금 처리할 문서를 엽니다.</li><li>오류가 나면 표시된 항목을 고칩니다. 입력값은 유지합니다.</li></ol><h2>처음 준비하는 관리자</h2><p><a href="#setup">회사 시작 안내</a>에서 준비 순서와 남은 조건을 확인합니다.</p><h2>설계의 한계</h2><p>이 시제품은 서버 인증·권한·저장·백업을 구현하지 않습니다. 실제 제품에서는 서버가 매 요청마다 권한과 현재 상태를 검사해야 합니다.</p></section>`,
      login: () =>
        heading(
          "로그인 단계 검토",
          "비밀번호 확인 후 두 번째 인증을 마치기 전에는 업무 세션을 발급하지 않는 설계입니다.",
        ) +
        `<section class="card compact"><h2>인증 앱의 번호를 입력하세요</h2><p class="muted">시제품에는 실제 계정이 없습니다.6자리 입력의 화면 흐름만 확인합니다.</p>${otpForm("login-code", "확인 흐름 보기")}</section>`,
    };
    main.innerHTML = (views[route] || views.home)();
    state.menu = false;
    nav.classList.remove("open");
    document
      .querySelector("#menu-toggle")
      .setAttribute("aria-expanded", "false");
  }
  function otpForm(id, label) {
    return `<form data-form="otp" novalidate><div class="error-summary" role="alert"></div><div class="field"><label for="${id}">인증 번호</label><input id="${id}" name="otp" inputmode="numeric" autocomplete="off" maxlength="6" aria-describedby="${id}-hint ${id}-error"><span id="${id}-hint" class="hint">검토용 · 숫자 6자리를 입력하세요. 실제 인증하지 않습니다.</span><span id="${id}-error" class="error"></span></div><button class="primary" type="submit">${label}</button></form>`;
  }
  const actions = {
    "review-doc": () =>
      open(
        "문서 검토 · 합성 예시",
        '<p class="muted">일반 기안 · 공구 구매 검토</p><h3>요청 내용</h3><p>금형 유지보수용 공구 구매의 필요성과 금액을 확인합니다.</p><div class="notice">실제 제품에서는 본인에게 허용된 처리만 표시하고 서버가 다시 확인합니다.</div><div class="actions">' +
          button("승인 전 확인 보기", "approval", true) +
          button("닫기", "discard") +
          "</div>",
      ),
    approval: () => {
      document.querySelector("#dialog-title").textContent = "승인 전 확인";
      document.querySelector("#dialog-body").innerHTML =
        '<p>승인은 처리 기록으로 남습니다. 입력한 문서 내용과 결재 범위를 다시 확인하세요.</p><div class="notice">시제품이므로 실제 승인하지 않습니다.</div>' +
        button("문서로 돌아가기", "discard", true);
    },
    draft: () =>
      open(
        "새 기안 · 검토용",
        `<form data-form="draft" novalidate><div class="error-summary" role="alert"></div><div class="field"><label for="draft-title">제목</label><input id="draft-title" name="title" maxlength="120" aria-describedby="draft-title-error"><span id="draft-title-error" class="error"></span></div><div class="field"><label for="draft-body">설명</label><input id="draft-body" name="body" maxlength="500"></div><p class="muted">제품의 실제 초안 저장 기능이 아닙니다.</p><div class="actions"><button class="primary">초안 저장 흐름 보기</button>${button("취소", "ask-close")}</div></form>`,
      ),
    enroll: () =>
      open(
        "인증 앱 등록 · 검토용",
        `<ol><li>현재 비밀번호로 본인 확인</li><li>인증 앱에서 QR 또는 설정 키 등록</li><li>6자리 번호 확인</li><li>백업 코드 보관</li></ol><div class="qr" role="img" aria-label="시제품용 QR 자리, 실제 등록 불가"><span>QR 표시 위치<br>실제 등록 불가</span></div>${otpForm("enroll-code", "등록 확인 흐름 보기")}`,
      ),
    codes: () =>
      open(
        "백업 코드 보관 · 검토용",
        `<p>실제 제품에서는 발급 직후 한 번만 보여 주고 서버에는 원문을 저장하지 않습니다.</p><div class="codes">${Array.from({ length: 8 }, (_, i) => `<span>DEMO-ONLY-${String(i + 1).padStart(4, "0")}</span>`).join("")}</div><p class="muted">위 값은 사용할 수 없는 시제품 표시입니다. 실제 제품은 외부 QR 서비스나 브라우저 영구 저장소로 비밀을 보내지 않습니다.</p><label class="check"><input id="code-check" type="checkbox">실제 제품에서 이 코드를 안전한 별도 장소에 보관해야 함을 확인했습니다.</label><button class="primary" data-action="codes-done" disabled>보관 확인 흐름 마치기</button>`,
      ),
    "codes-done": () => {
      state.codesSaved = true;
      close();
      notice(
        "시제품: 백업 코드 보관 확인 장면을 검토했습니다. 실제 코드는 발급하지 않았습니다.",
      );
    },
    invite: () =>
      open(
        "본인 연결 안내",
        `<p>직원이 자기 로그인에서 사번·이름·부서를 확인하고 직접 동의합니다. 관리자가 대신 수락할 수 없습니다.</p><div class="notice">예시 직원09 · SYN-010 · 운영팀</div>${button("검토 마치기", "discard", true)}`,
      ),
    scope: () =>
      open(
        "허용 범위 보기",
        `<p>일반 직원은 본인 기안과 허용된 결재·공지·일정·채팅을 사용합니다. 직무 명칭만으로 관리자 권한을 얻지 않습니다.</p><p>권한을 바꾸는 경우 현재 보안 관리자의 추가 인증·변경 사유·버전 확인이 필요합니다.</p>${button("검토 마치기", "discard", true)}`,
      ),
    "policy-edit": () =>
      open(
        "다음 기준 검토 · 시제품",
        `<form data-form="policy" novalidate><div class="error-summary" role="alert"></div><div class="fields">${[
          ["interval", "백업 간격 (분)", 5, 1440],
          ["rpo", "허용 데이터 손실 (분)", 1, 1440],
          ["rto", "복구 목표 (분)", 15, 10080],
          ["docs", "문서 보관 (개월)", 1, 120],
          ["audit", "보안 기록 보관 (개월)", 1, 120],
          ["backup", "백업 보관 (일)", 7, 365],
        ]
          .map(
            ([key, label, min, max]) =>
              `<div class="field"><label for="policy-${key}">${label}</label><input id="policy-${key}" name="${key}" type="number" min="${min}" max="${max}" value="${escape(state.policy[key])}" aria-describedby="policy-${key}-error"><span id="policy-${key}-error" class="error"></span></div>`,
          )
          .join(
            "",
          )}</div><div class="field"><label for="policy-reason">검토 사유</label><input id="policy-reason" name="reason" aria-describedby="policy-reason-error"><span id="policy-reason-error" class="error"></span></div><div class="notice">값은 이 시제품 안에서만 반영되며 실제 회사 정책을 바꾸지 않습니다.</div><div class="actions"><button class="primary">검토값을 화면에 반영</button>${button("취소", "ask-close")}</div></form>`,
      ),
    pilot: () =>
      open(
        "시범 전환 전 확인",
        `<p>연결·MFA·복구 수단·보관 기준·검증된 복원 기록·담당자 확인 중 하나라도 부족하면 서버가 전환을 거부합니다.</p><p>직원이 연결을 끊거나 복원 증거가 만료되면 현재 상태를 다시 계산합니다. 화면 체크나 오래된 성공 기록만으로 전환하지 않습니다.</p><div class="notice warn">이 시제품에서는 실제 운영 전환을 할 수 없습니다.</div>${button("남은 조건으로 돌아가기", "discard", true)}`,
      ),
    "backup-info": () =>
      open(
        "백업 기록의 확인 항목",
        `<ul><li>실행 ID·기준 코드·DB head·시각</li><li>파일 지문과 암호화 키 식별자(비밀 값 제외)</li><li>별도 저장소의 기록과 최신 백업 나이</li><li>서버가 검증한 실행 서명</li></ul><p>누락·위조·오래된 결과는 준비 완료로 표시하지 않습니다.</p>${button("닫기", "discard")}`,
      ),
    restore: () =>
      open(
        "복원 결과 예시 · 실제 실행 아님",
        `<p class="muted">시제품의 확인 항목입니다. 실제 검사 결과가 아닙니다.</p><div class="row"><span>원장·연결·역할·사건 대조</span><span>행 수와 지문 필요</span></div><div class="row"><span>기존 세션 무효화</span><span>이전 세션 거부 확인</span></div><div class="row"><span>백업 이후 권한 회수</span><span>회수 목록 재적용</span></div><div class="row"><span>실제 복구 시간 / 손실 범위</span><span>목표와 비교</span></div>${button("검토 마치기", "discard", true)}`,
      ),
    "retention-review": () =>
      open(
        "보관 검토 절차",
        `<ol><li>현재 열람 권한과 보존 중지 여부 확인</li><li>문서 소유자·회사 담당자가 보관 기준 검토</li><li>원본과 사건 이력을 검증 가능한 보관본으로 준비</li><li>보관본 복원 검증과 검토 이력 기록</li></ol><p>기본 범위는 보관 검토와 보존 중지까지입니다. 원본·확정 이력 자동 삭제는 제공하지 않습니다.</p>${button("닫기", "discard")}`,
      ),
    recover: () =>
      open(
        "백업 코드로 복구 · 검토용",
        `<ol><li>현재 비밀번호 확인</li><li>아직 사용하지 않은 백업 코드 확인</li><li>제한된 복구 화면에서 새 인증 앱 등록</li><li>기존 세션·이전 복구 수단 무효화</li><li>새 로그인으로 업무 시작</li></ol><p>실제 백업 코드를 이 시제품에 입력하지 마세요.</p>${button("로그인 단계 화면 보기", "login-view", true)}`,
      ),
    assisted: () =>
      open(
        "회사 복구 요청 절차",
        `<p>현재 회사가 지정한 담당자에게 요청하고 본인 확인을 거칩니다. 비밀번호나 다른 직원의 코드를 받는 방식은 사용하지 않습니다.</p><p>운영자는 승인된 만료형 복구 요청만 발급하고, 완료 시 기존 세션을 무효화합니다. 운영자가 본인으로 가장하는 세션은 만들지 않습니다.</p>${button("검토 마치기", "discard", true)}`,
      ),
    emergency: () =>
      open(
        "관리자 긴급 복구 준비",
        `<p>유일한 관리자의 계정 분실은 다른 직원의 권한 자동 승격으로 해결하지 않습니다.</p><ol><li>서비스 DB와 분리해 긴급 복구 수단 보관</li><li>회사 소유자 확인과 서버 운영 권한 확인</li><li>사유·만료가 있는 복구 요청 발급</li><li>비밀번호·MFA 재등록과 세션 회수</li><li>복구 이력을 별도 보관하고 업무 재확인</li></ol><p>비밀과 키까지 모두 분실하면 복구를 보장할 수 없습니다. 창업 시 책임자와 보관 장소를 실제로 정해야 합니다.</p>${button("닫기", "discard")}`,
      ),
    "login-view": () => {
      close();
      location.hash = "login";
    },
    "demo-work": () =>
      notice(
        "시제품: 현재 제품의 공지·일정·채팅으로 연결할 위치입니다. 실제 업무는 처리하지 않았습니다.",
      ),
    resume,
    discard: close,
    "ask-close": askClose,
  };
  document.addEventListener("click", (e) => {
    if (e.target.closest(".skip")) {
      e.preventDefault();
      main.focus();
      return;
    }
    const b = e.target.closest("[data-action]");
    if (b && !b.disabled) actions[b.dataset.action]?.();
  });
  document.addEventListener("input", (e) => {
    if (dialog.open && e.target.matches("input")) dirty = true;
    if (e.target.id === "code-check")
      dialog.querySelector("[data-action=codes-done]").disabled =
        !e.target.checked;
  });
  document.addEventListener("submit", (e) => {
    const form = e.target;
    if (!form.matches("form[data-form]")) return;
    e.preventDefault();
    form.querySelector(".error-summary").textContent = "";
    form
      .querySelectorAll("[aria-invalid]")
      .forEach((i) => i.removeAttribute("aria-invalid"));
    form.querySelectorAll(".error").forEach((i) => (i.textContent = ""));
    if (form.dataset.form === "otp") {
      const i = form.querySelector("[name=otp]");
      if (!/^\d{6}$/.test(i.value)) {
        error(form, "인증 번호는 숫자 6자리로 입력하세요.", i.id);
        return;
      }
      if (dialog.open) {
        state.mfaScene = true;
        close();
        render();
      } else {
        form.innerHTML =
          '<div class="notice">시제품: 두 번째 인증 다음 화면입니다. 실제 업무 세션은 발급하지 않았습니다.</div><a href="#home">내 업무 화면 보기</a>';
      }
      notice("시제품의 화면 전환입니다. 실제 인증 성공이 아닙니다.");
    }
    if (form.dataset.form === "draft") {
      if (!form.elements.title.value.trim()) {
        error(
          form,
          "제목을 입력하세요. 기존 설명은 유지됩니다.",
          "draft-title",
        );
        return;
      }
      close();
      notice(
        "시제품: 초안 저장 후 목록으로 돌아갈 위치를 확인했습니다. 실제 저장하지 않았습니다.",
      );
    }
    if (form.dataset.form === "policy") {
      for (const key of ["interval", "rpo", "rto", "docs", "audit", "backup"]) {
        const i = form.elements[key],
          n = Number(i.value);
        if (!Number.isInteger(n) || n < Number(i.min) || n > Number(i.max)) {
          error(
            form,
            `${i.previousElementSibling.textContent}: ${i.min}~${i.max} 사이의 정수를 입력하세요.`,
            i.id,
          );
          return;
        }
      }
      if (
        Number(form.elements.interval.value) >= Number(form.elements.rpo.value)
      ) {
        error(
          form,
          "백업 간격은 허용 데이터 손실 시간보다 짧아야 합니다.",
          "policy-interval",
        );
        return;
      }
      if (form.elements.reason.value.trim().length < 2) {
        error(form, "검토 사유를 2자 이상 입력하세요.", "policy-reason");
        return;
      }
      for (const key of Object.keys(state.policy))
        state.policy[key] = form.elements[key].value;
      state.draft = true;
      close();
      render();
      notice(
        "검토값만 이 시제품에 반영했습니다. 실제 저장·운영 전환은 하지 않았습니다.",
      );
    }
  });
  document.querySelector("#close-dialog").addEventListener("click", askClose);
  dialog.addEventListener("cancel", (e) => {
    e.preventDefault();
    askClose();
  });
  document.querySelector("#menu-toggle").addEventListener("click", () => {
    state.menu = !state.menu;
    nav.classList.toggle("open", state.menu);
    document
      .querySelector("#menu-toggle")
      .setAttribute("aria-expanded", String(state.menu));
  });
  role.addEventListener("change", () => {
    render();
    notice(
      "검토할 화면만 바뀌었습니다. 실제 계정의 역할을 변경하지 않았습니다.",
    );
  });
  window.addEventListener("hashchange", () => {
    render();
    main.focus();
  });
  render();
})();

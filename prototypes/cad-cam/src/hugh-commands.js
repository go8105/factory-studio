export function parseHughCommand(value) {
  const text = String(value)
    .toLowerCase()
    .replace(/[.,!?\-]/g, " ")
    .replace(/\s+/g, "")
    .trim();
  const wake =
    /헤이(?:와이씨|와이시|yc)|hey(?:yc|와이씨)|헤이(?:휴디|휴디디|휴디이|휴디야)|hey(?:hughd|hugh디|휴디|hudy)|헤이휴디/.test(
      text,
    );
  const rest = text.replace(
    /헤이(?:와이씨|와이시|yc|휴디디|휴디이|휴디야|휴디)|hey(?:yc|와이씨|hughd|hugh디|휴디|hudy)/g,
    "",
  );
  if (/하지마|하지말|말고|취소|하지않/.test(rest))
    return { wake, type: "unknown" };
  if (/마이크(?:꺼|종료)|음성(?:꺼|종료)/.test(rest))
    return { wake, type: "off" };
  if (/멈춰|정지|중지|일시정지/.test(rest)) return { wake, type: "stop" };
  if (/제안|최적안|추천/.test(rest)) return { wake, type: "propose" };
  if (/실행|재생|시작/.test(rest)) {
    const match = rest.match(
      /(\d+|열세|열두|열한|열|아홉|여덟|일곱|여섯|다섯|네|넷|세|셋|두|둘|한|하나|일|이|삼|사|오|육|칠|팔|구)번(?:째)?/,
    );
    const numbers = {
      열세: 13,
      열두: 12,
      열한: 11,
      열: 10,
      아홉: 9,
      여덟: 8,
      일곱: 7,
      여섯: 6,
      다섯: 5,
      네: 4,
      넷: 4,
      세: 3,
      셋: 3,
      두: 2,
      둘: 2,
      한: 1,
      하나: 1,
      일: 1,
      이: 2,
      삼: 3,
      사: 4,
      오: 5,
      육: 6,
      칠: 7,
      팔: 8,
      구: 9,
    };
    return {
      wake,
      type: match ? "play" : "unknown",
      number: match ? (numbers[match[1]] ?? Number(match[1])) : null,
    };
  }
  return { wake, type: wake && !rest ? "wake" : "unknown" };
}
// Recognition events may repeat the same final result; a session+index identifies it.
export class HughCommands {
  constructor(actions, now = () => Date.now()) {
    this.actions = actions;
    this.now = now;
    this.until = 0;
    this.seen = new Set();
  }
  reset() {
    this.until = 0;
    this.seen.clear();
  }
  accept(text, key, manual = false) {
    if (this.seen.has(key)) return null;
    this.seen.add(key);
    if (this.seen.size > 128) this.seen.delete(this.seen.values().next().value);
    const command = parseHughCommand(text);
    if (command.wake) this.until = this.now() + 30000;
    if (!manual && this.now() >= this.until) return null;
    if (command.type === "wake") return "네, 무엇을 도와드릴까요?";
    if (command.type === "off") {
      this.reset();
      this.actions.off();
      return "마이크를 껐습니다";
    }
    if (command.type === "stop") {
      this.actions.stop();
      this.until = this.now() + 30000;
      return "시뮬레이션을 멈췄습니다";
    }
    if (command.type === "propose") {
      const reply = this.actions.propose();
      this.until = this.now() + 30000;
      return reply;
    }
    if (command.type === "play") {
      const reply = this.actions.play(command.number);
      this.until = this.now() + 30000;
      return reply;
    }
    return "제안해줘, 2번 시뮬레이션 실행해줘, 멈춰라고 말씀하세요";
  }
}

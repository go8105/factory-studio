// P-08 휴일 달력 — 회사 공통 달력(core). BEMS 운전 스케줄·FEMS TOU 요금·HR 근태가 같은 날짜를 읽는다.
// 공휴일은 시드가 넣어 두고, 회사 휴무는 여기서 더한다. 요일 구분은 휴일 > 토·일 > 평일이다.
import { useState } from "react";
import { MasterScreen, type MasterSpec } from "../shared/master";
import { useSession } from "../app/session";

export type Holiday = {
  id: number;
  date: string;
  name: string;
  kind: "PUBLIC" | "COMPANY";
};
type Draft = { date: string; name: string; kind: Holiday["kind"] };

const KIND_LABEL: Record<Holiday["kind"], string> = {
  PUBLIC: "공휴일",
  COMPANY: "회사 휴무",
};
const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];
/** 'YYYY-MM-DD'를 그대로 읽는다 — Date 파싱은 시간대에 따라 하루가 밀린다. */
const weekdayOf = (iso: string) =>
  WEEKDAYS[new Date(`${iso}T00:00:00Z`).getUTCDay()];

export function Holidays() {
  const { session } = useSession();
  const thisYear = new Date().getFullYear();
  const [year, setYear] = useState(thisYear);
  // 회원 공간(회사 달력)은 관리자만 고친다. 체험 공간은 본인 달력이라 누구나 고친다.
  const readOnly =
    session?.actorKind === "MEMBER" && !session.roles.includes("ADMIN");
  const years = [thisYear - 1, thisYear, thisYear + 1];
  const spec: MasterSpec<Holiday, Draft> = {
    id: "P-08",
    title: "휴일 달력",
    subtitle:
      "회사 공통 휴일입니다. BEMS 운전 스케줄·FEMS 요금·HR 근태가 이 날짜를 함께 읽습니다" +
      (readOnly ? " · 관리자만 고칠 수 있습니다" : ""),
    help: "portal/p-08",
    base: "/holidays",
    requestQuery: `year=${year}`,
    readOnly,
    limit: 50,
    blank: { date: "", name: "", kind: "COMPANY" },
    actions: (
      <select
        aria-label="조회 연도"
        value={year}
        onChange={(e) => setYear(Number(e.target.value))}
      >
        {years.map((y) => (
          <option key={y} value={y}>
            {y}년
          </option>
        ))}
      </select>
    ),
    intro: (
      <p className="muted">
        요일 구분은 휴일 &gt; 토·일 &gt; 평일 순서입니다. 토·일은 여기 없어도
        주말로 봅니다.
      </p>
    ),
    columns: [
      // 요일은 날짜 칸에 함께 적는다 — 표의 열 key는 유일해야 한다(관리 열이 id를 쓴다).
      {
        key: "date",
        label: "날짜",
        render: (r) => `${r.date} (${weekdayOf(r.date)})`,
      },
      { key: "name", label: "이름" },
      { key: "kind", label: "구분", render: (r) => KIND_LABEL[r.kind] },
    ],
    fields: [
      { kind: "text", key: "date", label: "날짜 (YYYY-MM-DD)", required: true },
      {
        kind: "text",
        key: "name",
        label: "이름",
        required: true,
        maxLength: 60,
      },
      { kind: "select", key: "kind", label: "구분", options: KIND_LABEL },
    ],
    labels: {
      create: "휴일 등록",
      caption: `${year}년 휴일`,
      emptyReason: "이 해에 등록한 휴일이 없습니다.",
      editTitle: (r) => `${r.date} ${r.name}`,
      deleted: (r) => `${r.date} ${r.name}을(를) 삭제했습니다.`,
      moduleOff: "휴일 달력을 열 수 없습니다.",
    },
  };
  return <MasterScreen spec={spec} />;
}

// C-08 정비원·외주 업체 — 작업지시의 담당자와 외주처 (UI-03 S 패턴, DSN-21 Q5).
// 인사 정보는 HR이 갖고 여기엔 사원 코드만 스냅샷으로 둔다(D79). 거래처도 ERP 코드만 들고 있는다.
import { useState } from "react";
import { Badge, type Column } from "../shared/components";
import { CODE_PATTERN, MasterScreen, type MasterSpec } from "../shared/master";
import {
  CMMS,
  SKILL_LABEL,
  money,
  type Skill,
  type Technician,
  type Vendor,
} from "./common";

type TechDraft = {
  code: string;
  name: string;
  skill: Skill;
  hourlyRate: string;
  hrEmployeeCode: string;
  isActive: boolean;
};
type VendorDraft = {
  code: string;
  name: string;
  erpPartnerCode: string;
  phone: string;
  isActive: boolean;
};

const used = <T extends { isActive: boolean }>(): Column<T> => ({
  key: "isActive",
  label: "사용",
  render: (r) => (
    <Badge tone={r.isActive ? "normal" : "warning"}>
      {r.isActive ? "사용" : "사용 안 함"}
    </Badge>
  ),
});

const techSpec: MasterSpec<Technician, TechDraft> = {
  id: "C-08",
  title: "정비원",
  subtitle: "작업지시 담당자와 시간당 인건비입니다",
  help: "cmms/c-08",
  base: `${CMMS}/technicians`,
  blank: {
    code: "",
    name: "",
    skill: "MECHANICAL",
    hourlyRate: "30000",
    hrEmployeeCode: "",
    isActive: true,
  },
  intro: (
    <p role="note" className="muted">
      시간당 인건비는 <strong>보전 비용 집계에만</strong> 쓰는 값입니다. 실제
      급여는 HR이 계산하고, 여기 값은 "이 고장을 고치는 데 얼마가 들었나"를
      어림하기 위한 것입니다.
    </p>
  ),
  columns: [
    { key: "code", label: "코드" },
    { key: "name", label: "이름" },
    { key: "skill", label: "분야", render: (r) => SKILL_LABEL[r.skill] },
    {
      key: "hourlyRate",
      label: "시간당 인건비",
      render: (r) => money(r.hourlyRate),
    },
    {
      key: "hrEmployeeCode",
      label: "HR 사원",
      render: (r) => r.hrEmployeeCode ?? "—",
    },
    used<Technician>(),
  ],
  fields: [
    {
      kind: "text",
      key: "code",
      label: "코드",
      required: true,
      maxLength: 20,
      pattern: CODE_PATTERN,
      title: "영문 대문자로 시작하는 2~20자",
      upper: true,
    },
    {
      kind: "text",
      key: "name",
      label: "이름",
      required: true,
      maxLength: 100,
    },
    { kind: "select", key: "skill", label: "분야", options: SKILL_LABEL },
    {
      kind: "text",
      key: "hourlyRate",
      label: "시간당 인건비(원)",
      required: true,
    },
    {
      kind: "text",
      key: "hrEmployeeCode",
      label: "HR 사원 코드(선택)",
      maxLength: 30,
      title:
        "HR에 있는 사원과 잇고 싶을 때만 적습니다. 인사 정보는 HR이 갖습니다.",
    },
    { kind: "check", key: "isActive", label: "사용" },
  ],
  labels: {
    create: "정비원 등록",
    caption: "정비원",
    emptyReason: "정비원이 없습니다. 담당자를 적으려면 먼저 등록하세요.",
    editTitle: (row) => `${row.name} 수정`,
    deleted: (row) => `${row.name}을(를) 삭제했습니다.`,
    moduleOff:
      "CMMS를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다.",
  },
};

const vendorSpec: MasterSpec<Vendor, VendorDraft> = {
  id: "C-08",
  title: "외주 업체",
  subtitle: "외주 수리를 맡기는 업체입니다",
  help: "cmms/c-08",
  base: `${CMMS}/vendors`,
  blank: {
    code: "",
    name: "",
    erpPartnerCode: "",
    phone: "",
    isActive: true,
  },
  intro: (
    <p role="note" className="muted">
      외주 비용은 작업지시 완료 때 적습니다. <strong>회계 처리는 ERP</strong>
      에서 직접 매입으로 따로 하고, CMMS는 보전 비용을 집계할 때만 이 금액을
      씁니다.
    </p>
  ),
  columns: [
    { key: "code", label: "코드" },
    { key: "name", label: "업체명" },
    {
      key: "erpPartnerCode",
      label: "ERP 거래처",
      render: (r) => r.erpPartnerCode ?? "—",
    },
    { key: "phone", label: "연락처", render: (r) => r.phone ?? "—" },
    used<Vendor>(),
  ],
  fields: [
    {
      kind: "text",
      key: "code",
      label: "코드",
      required: true,
      maxLength: 20,
      pattern: CODE_PATTERN,
      title: "영문 대문자로 시작하는 2~20자",
      upper: true,
    },
    {
      kind: "text",
      key: "name",
      label: "업체명",
      required: true,
      maxLength: 200,
    },
    {
      kind: "text",
      key: "erpPartnerCode",
      label: "ERP 거래처 코드(선택)",
      maxLength: 40,
      title: "ERP 매입처와 잇고 싶을 때만 적습니다.",
    },
    { kind: "text", key: "phone", label: "연락처(선택)", maxLength: 30 },
    { kind: "check", key: "isActive", label: "사용" },
  ],
  labels: {
    create: "외주 업체 등록",
    caption: "외주 업체",
    emptyReason: "외주 업체가 없습니다. 직접 수리만 한다면 없어도 됩니다.",
    editTitle: (row) => `${row.name} 수정`,
    deleted: (row) => `${row.name}을(를) 삭제했습니다.`,
    moduleOff:
      "CMMS를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다.",
  },
};

export function Technicians() {
  const [tab, setTab] = useState<"tech" | "vendor">("tech");
  return (
    <>
      <div className="filter-bar" role="tablist" aria-label="정비원·외주 업체">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "tech"}
          onClick={() => setTab("tech")}
        >
          정비원
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "vendor"}
          onClick={() => setTab("vendor")}
        >
          외주 업체
        </button>
      </div>
      {tab === "tech" ? (
        <MasterScreen key="tech" spec={techSpec} />
      ) : (
        <MasterScreen key="vendor" spec={vendorSpec} />
      )}
    </>
  );
}

import { PageTitle } from "../shared/components";
import { Master, type InputField } from "./Master";
const departments: InputField[] = [
  { key: "code", label: "부서 코드", maxLength: 30 },
  { key: "name", label: "부서명", maxLength: 100 },
  {
    key: "costCenterKind",
    label: "원가 구분",
    options: [
      ["MFG", "제조"],
      ["SALES", "판매"],
      ["ADMIN", "관리"],
    ],
    initial: "ADMIN",
  },
  { key: "isActive", label: "사용 여부", type: "checkbox" },
];
const employees: InputField[] = [
  { key: "code", label: "담당자 코드", maxLength: 30 },
  { key: "name", label: "이름", maxLength: 100 },
  {
    key: "departmentId",
    label: "부서",
    lookup: { path: "/api/v1/erp/departments", code: "code", name: "name" },
  },
  { key: "hrEmployeeCode", label: "HR 사번", nullable: true, maxLength: 30 },
  { key: "isActive", label: "사용 여부", type: "checkbox" },
];
const projects: InputField[] = [
  { key: "code", label: "프로젝트 코드", maxLength: 30 },
  { key: "name", label: "프로젝트명", maxLength: 200 },
  { key: "startOn", label: "시작일", type: "date", nullable: true },
  { key: "endOn", label: "종료일", type: "date", nullable: true },
  { key: "isActive", label: "사용 여부", type: "checkbox" },
];
export function Organization() {
  return (
    <div className="page-fill">
      <PageTitle id="E-19" title="부서·담당자·프로젝트" help="erp/e-19" />
      <p className="muted" role="note">
        전표와 문서의 관리항목입니다. HR 조직과 별개로 ERP가 직접 가집니다 —
        코드가 같아도 다른 데이터이고, HR 사번은 맞춰 보기 위한 메모일 뿐
        무결성을 강제하지 않습니다. 부서의 원가 구분은 결산에서 제조원가와
        판매비·관리비를 가르는 기준입니다.
      </p>
      <Master
        embedded
        id="E-19"
        title="부서"
        path="/api/v1/erp/departments"
        fields={departments}
      />
      <Master
        embedded
        id="E-19"
        title="담당자"
        path="/api/v1/erp/employees"
        fields={employees}
      />
      <Master
        embedded
        id="E-19"
        title="프로젝트"
        path="/api/v1/erp/projects"
        fields={projects}
      />
    </div>
  );
}

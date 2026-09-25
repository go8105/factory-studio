import { Master, type InputField } from "./Master";
const fields: InputField[] = [
  {key:"partnerCode",label:"거래처 코드",maxLength:40},
  {key:"partnerName",label:"거래처명",maxLength:200},
  {key:"partnerKind",label:"거래처 구분",options:[["CUSTOMER","매출처"],["SUPPLIER","매입처"]],initial:"CUSTOMER"},
  {key:"paymentTermDays",label:"결제조건 일수",type:"number",nullable:true},
  {key:"isActive",label:"사용 여부",type:"checkbox"},
];
export function Partners(){return <Master id="E-15" title="거래처" path="/api/v1/erp/partners" fields={fields} note="결제조건을 비워 두면 만기 미설정으로 취급합니다. 참조 중인 거래처는 삭제 대신 사용 여부를 변경할 수 있습니다."/>;}

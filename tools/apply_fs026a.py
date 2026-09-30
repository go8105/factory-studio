"""FS-026a additive WMS metadata. Frozen migrations do not import this module.

2026-09-30 main 병합: FS-028a(SPC, v0.13.0) 뒤에 적용해 v0.14.0이 된다. 마이그레이션도 fs028b_spc_module 다음이다.
"""
import copy
import json
from pathlib import Path
from apply_fs023a import S, c, col, r, table, uk_partial

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / 'docs/db/schema-metadata/schema.json'
N, L, C, R, B = ['wms.' + n for n in ('inbound_notice', 'inbound_notice_line', 'source_claim', 'stock_reservation', 'stock_reservation_line')]
SL, SD = 'wms.storage_location', 'wms.stock_document'

def field(name, label, type_, nullable=False, default=None):
    return col(name, label, type_, nullable=nullable, default=default)

def entity(name, label, fields):
    t = table(name, label, 'receiving' if name in (N,L,C) else 'reservation', 'FS-026 revision 2; SERVICE 정책은 후속 API에서 구현', fields)
    t['phase'] = 'W2'
    t['columns'][-1]['default'] = 'clock_timestamp()'
    return t

TABLES = [
    entity(N, '입고 예정·검수', [
        field('notice_no','입고 번호','varchar(40)'), field('business_key','업무 중복 방지 번호','varchar(100)'),
        field('warehouse_id','창고','bigint'), field('status','상태','varchar(16)',default="'PLANNED'"),
        field('expected_on','예정일','date'), field('vehicle_no','차량 번호','varchar(40)',True),
        field('partner_ref','공급처 참고','varchar(100)',True), field('version','변경 버전','integer',default='1'),
        field('arrived_at','도착 시각','timestamptz',True), field('inspected_at','검수 시각','timestamptz',True),
        field('cancelled_at','취소 시각','timestamptz',True), field('stock_document_id','검수 전표','bigint',True),
        field('reason','사유','varchar(300)',True), field('updated_at','변경 시각','timestamptz',default='clock_timestamp()'),
    ]),
    entity(L, '입고 예정·검수 명세', [
        field('notice_id','입고 예정','bigint'), field('line_no','줄 번호','integer'), field('item_id','품목','bigint'),
        field('lot_no','완제품 LOT','varchar(50)',True), field('expected_qty','예정 수량','numeric(18,3)'),
        field('accepted_qty','합격 수량','numeric(18,3)',True), field('quarantined_qty','격리 수량','numeric(18,3)',True),
        field('shortage_qty','부족 수량','numeric(18,3)',True), field('normal_location_id','정상 위치','bigint'),
        field('quarantine_location_id','격리 위치','bigint',True), field('reason','격리·부족 사유','varchar(300)',True),
    ]),
    entity(C, '매입 원천 선점·대사', [
        field('source_key','ERP 매입 원천 키','varchar(100)'), field('notice_id','입고 예정','bigint'),
        field('status','상태','varchar(16)',default="'CLAIMED'"), field('source_snapshot','원천 환산 스냅샷','jsonb'),
        field('source_digest','스냅샷 해시','varchar(64)'), field('closed_at','완료·해제 시각','timestamptz',True),
        field('release_reason','해제 사유','varchar(300)',True),
    ]),
    entity(R, '출고 예약', [
        field('reservation_no','예약 번호','varchar(40)'), field('business_key','업무 중복 방지 번호','varchar(100)'),
        field('status','상태','varchar(16)',default="'ACTIVE'"), field('shipment_order_ref','ERP 출하지시 참고','varchar(40)',True),
        field('version','변경 버전','integer',default='1'), field('reason','사유','varchar(300)',True),
        field('closed_at','해제·소진 시각','timestamptz',True), field('shipment_source_key','소진 출하 원천','varchar(100)',True),
        field('stock_document_id','출하 차감 전표','bigint',True),
    ]),
    entity(B, '예약 배분', [
        field('reservation_id','예약','bigint'), field('line_no','줄 번호','integer'), field('item_id','품목','bigint'),
        field('location_id','정상 위치','bigint'), field('lot_no','완제품 LOT','varchar(50)',True),
        field('quantity','예약 수량','numeric(18,3)'),
    ]),
]
CONSTRAINTS = []
def ck(t, cols, expr, reason):
    CONSTRAINTS.append(c(t,'CHECK',cols,expr,reason))
def uk(t, cols):
    CONSTRAINTS.append(c(t,'UK',S+cols,reason='세대 내 유일'))
def partial(t, cols, pred, reason):
    CONSTRAINTS.append(uk_partial(t,cols,pred,reason))
for t in TABLES:
    CONSTRAINTS.extend([c(t['name'],'PK',['id'],reason='기본키'),c(t['name'],'UK',S+['id'],reason='범위 참조 대상')])
for t, name in [(N,'notice_no'),(R,'reservation_no')]:
    uk(t,[name]); uk(t,['business_key'])
    ck(t,[name,'business_key'],f"length(btrim({name})) > 0 AND length(btrim(business_key)) > 0",'빈 업무 번호 금지')
    ck(t,['version'],'version > 0','낙관적 버전')
for t, values in [(N,['PLANNED','ARRIVED','INSPECTED','CANCELLED']),(C,['CLAIMED','COMPLETED','RELEASED']),(R,['ACTIVE','RELEASED','CONSUMED'])]:
    ck(t,['status'],'status IN ('+', '.join(repr(v) for v in values)+')','상태 값')
ck(N,['status','inspected_at'],"(status = 'INSPECTED') = (inspected_at IS NOT NULL)",'검수 시각')
ck(N,['status','cancelled_at'],"(status = 'CANCELLED') = (cancelled_at IS NOT NULL)",'취소 시각')
ck(N,['status','arrived_at'],"(status NOT IN ('ARRIVED','INSPECTED') OR arrived_at IS NOT NULL) AND (status <> 'PLANNED' OR arrived_at IS NULL)",'도착 시각')
ck(N,['status','stock_document_id'],"stock_document_id IS NULL OR status = 'INSPECTED'",'검수 전표 시점')
ck(N,['status','reason'],"status <> 'CANCELLED' OR (reason IS NOT NULL AND length(btrim(reason)) > 0)",'취소 사유')
partial(N,['stock_document_id'],'stock_document_id IS NOT NULL','검수 전표 중복 연결 금지')
for t, parent in [(L,'notice_id'),(B,'reservation_id')]:
    uk(t,[parent,'line_no']); ck(t,['line_no'],'line_no > 0','줄 번호')
    ck(t,['lot_no'],"lot_no IS NULL OR length(btrim(lot_no)) > 0",'빈 LOT 금지')
    cols=[parent,'item_id']+(['location_id'] if t==B else [])
    partial(t,cols,'lot_no IS NULL','원자재 NULL LOT 중복 방지')
    partial(t,cols+['lot_no'],'lot_no IS NOT NULL','완제품 LOT 중복 방지')
ck(L,['expected_qty'],'expected_qty > 0','양수 예정')
q=['accepted_qty','quarantined_qty','shortage_qty']
ck(L,q+['expected_qty'],'('+' AND '.join(f'{x} IS NULL' for x in q)+') OR ('+' AND '.join(f'{x} IS NOT NULL AND {x} >= 0' for x in q)+' AND accepted_qty + quarantined_qty + shortage_qty = expected_qty)','검수 수량 전체 입력 및 합계')
ck(L,['quarantined_qty','quarantine_location_id'],'quarantined_qty IS NULL OR quarantined_qty = 0 OR quarantine_location_id IS NOT NULL','격리 위치 필수')
ck(L,['quarantined_qty','shortage_qty','reason'],"NOT (coalesce(quarantined_qty,0) > 0 OR coalesce(shortage_qty,0) > 0) OR (reason IS NOT NULL AND length(btrim(reason)) > 0)",'차이 사유')
ck(B,['quantity'],'quantity > 0','양수 예약')
ck(C,['source_key'],"source_key ~ '^ERP:PURCHASE:.+$'",'매입 원천만')
ck(C,['source_snapshot'],"jsonb_typeof(source_snapshot) = 'object'",'원천 객체')
ck(C,['source_digest'],"source_digest ~ '^[0-9a-f]{64}$'",'SHA256 형식')
ck(C,['status','closed_at'],"(status = 'CLAIMED') = (closed_at IS NULL)",'선점 종료 시각')
ck(C,['status','release_reason'],"status <> 'RELEASED' OR (release_reason IS NOT NULL AND length(btrim(release_reason)) > 0)",'해제 사유')
for name in ['source_key','notice_id']:
    partial(C,[name],"status <> 'RELEASED'",'유효 원천·예정 연결은 1개')
ck(R,['status','closed_at'],"(status = 'ACTIVE') = (closed_at IS NULL)",'예약 종료 시각')
ck(R,['status','shipment_source_key','stock_document_id'],"(status = 'CONSUMED' AND shipment_source_key IS NOT NULL AND stock_document_id IS NOT NULL) OR (status <> 'CONSUMED' AND shipment_source_key IS NULL AND stock_document_id IS NULL)",'소진 전표와 원천 동시 기록')
ck(R,['shipment_source_key'],"shipment_source_key IS NULL OR shipment_source_key ~ '^ERP:SHIPMENT:.+$'",'출하 원천만')
ck(R,['status','reason'],"status <> 'RELEASED' OR (reason IS NOT NULL AND length(btrim(reason)) > 0)",'예약 해제 사유')
for name in ['shipment_source_key','stock_document_id']:
    partial(R,[name],f'{name} IS NOT NULL','출하 소진 1회')
ck(SL,['location_type'],"location_type IN ('NORMAL','QUARANTINE')",'위치 유형')
ck(SL,['location_type','is_default'],"NOT is_default OR location_type = 'NORMAL'",'기본 위치 정상만')
POLICIES = [
    (N,['status','stock_document_id'],'검수 완료 수령합>0이면 WMS_INSPECTION 전표 1개, 전량 부족이면 전표 없이 완료. 트럭은 도착만. 확정 후 불변','검수 원장 원자성'),
    (L,['notice_id','item_id','lot_no','normal_location_id','quarantine_location_id'],'같은 창고·정상/격리 유형, FG LOT 필수/RAW NULL, 검수 전 수량 NULL. 확인 후 불변','검수 위치 및 품목'),
    (C,['source_key','notice_id'],'공간 락에서 기존 원천 전표와 유효 선점을 함께 검사한다. 직접 반영과 검수 경유는 상호 배타. 완료 선점은 전량 부족도 영구 보존','원천 단일 경로'),
    (C,['source_snapshot','source_digest'],'연결 시 환산 스냅샷 고정, 확정 직전 interface로 취소/변경 재검증. 검수 완료 후 ERP 취소는 경고만. 기입고 대사는 원장 변화 없음','매입 실물 분리'),
    (R,['status','stock_document_id'],'원장 차감 없이 예약/해제. ERP 출하 전량·LOT 대사 성공 시 같은 TX에서 1회 차감과 소진. 소급 소진 금지','예약 소진 원자성'),
    (B,['quantity','location_id','item_id','lot_no'],'정상 현재고-활성예약 이상의 신규 예약 거부(공간 락). 원천 반영 음수는 허용/부족 경고. 원자재 LOT NULL, FG LOT 필수','예약 가능 수량'),
    (SL,['location_type'],'원장/진행 예정/활성 예약 참조 시 유형 변경 금지. 격리 이동 사유 필수. 진행 참조 위치 비활성 금지','위치 유형 보존'),
]
for t, cols, expression, reason in POLICIES:
    CONSTRAINTS.append(c(t,'SERVICE/DB_POLICY',cols,expression,reason))
RELATIONS = [dict(source=t['name'],columns=S,target='core.data_generation',target_columns=['workspace_id','id'],on_delete='RESTRICT',on_update='RESTRICT',note='세대 앵커') for t in TABLES]
for t, col_, target in [(N,'warehouse_id','warehouse'),(N,'stock_document_id','stock_document'),(L,'notice_id','inbound_notice'),(L,'item_id','item'),(L,'normal_location_id','storage_location'),(L,'quarantine_location_id','storage_location'),(C,'notice_id','inbound_notice'),(R,'stock_document_id','stock_document'),(B,'reservation_id','stock_reservation'),(B,'item_id','item'),(B,'location_id','storage_location')]:
    RELATIONS.append(r(t,[col_],'wms.'+target,'같은 공간·세대 참조'))
    CONSTRAINTS.append(c(t,'INDEX',S+[col_],reason='FK 조회'))
for t, cols in [(N,['status','expected_on']),(C,['source_key']),(R,['status']),(B,['item_id','location_id','lot_no'])]:
    CONSTRAINTS.append(c(t,'INDEX',S+cols,reason='업무 조회'))
STATES = [dict(table=t,column='status',values=vs,default=vs[0],transition=tr) for t,vs,tr in [(N,['PLANNED','ARRIVED','INSPECTED','CANCELLED'],'예정→도착→검수 또는 미확정 취소'),(C,['CLAIMED','COMPLETED','RELEASED'],'선점→완료/해제; 완료 불변'),(R,['ACTIVE','RELEASED','CONSUMED'],'활성→해제/소진; 종료 불변')]]

def apply(d):
    if N in {t['name'] for t in d['tables']}:
        return False
    for t in d['tables']:
        if t['name']==SL:
            t['columns'].append(col('location_type','위치 유형','varchar(16)',default="'NORMAL'",rule='NORMAL / QUARANTINE'))
        if t['name']==SD:
            for f in t['columns']:
                if f['name']=='document_type': f['rule']+=' / WMS_INSPECTION'
    # Existing CHECK identities remain stable; only allowed type sets expand.
    for x in d['constraints']:
        if x['table']==SD and x['kind']=='CHECK' and "'ERP_PURCHASE'" in x['expression']:
            x['expression']=x['expression'].replace("'ERP_PURCHASE'", "'ERP_PURCHASE', 'WMS_INSPECTION'")
    for x in d['code_lists']:
        if x['target']==SD and x['column']=='document_type': x['values'].append('WMS_INSPECTION')
    d['tables'].extend(copy.deepcopy(TABLES)); d['constraints'].extend(copy.deepcopy(CONSTRAINTS)); d['relations'].extend(copy.deepcopy(RELATIONS)); d['states'].extend(copy.deepcopy(STATES))
    d['code_lists'].append(dict(target=SL,column='location_type',values=['NORMAL','QUARANTINE'],default='NORMAL',note='격리는 현재고 포함·예약 제외'))
    d.update(version='0.14.0',task='FS-026a',date='2026-09-30',status='구현 명세 / 환경별 적용 상태는 인계 참조',migration_revision='fs026a_wms_receiving_reservation')
    d['change_log'].append(dict(version='0.14.0',task='FS-026a',date='2026-09-30',change='기존 WMS 확장: 입고 예정·명세·원천 선점·예약·배분 5테이블, 위치 유형 및 검수 전표(Codex 2026-09-28 설계, main 병합 때 FS-028a v0.13.0 뒤로 v0.14.0). 서비스 정책은 후속 API 대상',status='새 revision; DB 검증 결과는 인계 참조'))
    return True

if __name__=='__main__':
    d=json.loads(SCHEMA.read_text()); changed=apply(d)
    if changed: SCHEMA.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
    print({'changed':changed,'tables':len(d['tables']),'constraints':len(d['constraints']),'relations':len(d['relations'])})

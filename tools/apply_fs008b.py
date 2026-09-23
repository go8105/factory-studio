"""FS-008b: v0.8.0 -> v0.9.0 screen-design gaps; metadata only.

Validate before writing; SHA256 original backup; atomic replacement; --check;
validated repeat applications leave bytes and mtime unchanged.
"""
import copy
import json
from apply_fs014b import need, counts, col, S
from validate_db_design import validate, design_names

BEFORE = {'core': 11, 'mes': 21, 'erp': 27, 'fems': 13}
AFTER = dict(BEFORE, core=10)


def check(d, task):
    errors = validate(d, design_names(task))
    need(not errors, '\n'.join(errors))


def transform(original):
    need(original.get('version') == '0.8.0' and original.get('task') == 'FS-014b', 'Expected v0.8.0 / FS-014b')
    need(original.get('migration_revision') is None, 'DB-applied metadata is out of scope')
    need(counts(original) == BEFORE, 'Unexpected input counts')
    check(original, 'FS-014b')
    d = copy.deepcopy(original)
    tables = {t['name']: t for t in d['tables']}
    def field(t, c):
        return next(x for x in tables[t]['columns'] if x['name'] == c)
    def constraint(t, kind, cols, expression, reason):
        d['constraints'].append(dict(table=t,kind=kind,columns=cols,expression=expression,reason=reason))
    def policy(t, cols, expression, reason):
        constraint(t,'SERVICE/DB_POLICY',cols,expression,reason)

    # Replace target UK before rewiring consumers. All changes are one metadata replacement.
    oldkey = S + ['id','owner_module','unit']
    newkey = S + ['id','unit']
    keys = [c for c in d['constraints'] if c['table']=='fems.meter_channel' and c['kind']=='UK' and c['columns']==oldkey]
    need(len(keys)==1, 'Expected exactly one owner/unit channel UK')
    need(not any(c['table']=='fems.meter_channel' and c['kind']=='UK' and c['columns']==newkey for c in d['constraints']), 'Unexpected pre-existing replacement UK')
    keys[0].update(columns=newkey,reason='관측값·배분 결과의 채널 단위 일치 참조 대상')
    owners = {'fems.meter','fems.meter_channel','fems.energy_reading'}
    for name in owners:
        need(field(name,'owner_module')['type']=='varchar(10)', 'Unexpected owner type')
        tables[name]['columns'] = [c for c in tables[name]['columns'] if c['name']!='owner_module']
    kept=[]
    for c in d['constraints']:
        if c['table'] in owners and 'owner_module' in json.dumps(c):
            if c['table']=='fems.energy_reading' and c['kind']=='INDEX':
                c['columns']=[x for x in c['columns'] if x!='owner_module']
            else:
                need(c['kind'] in {'CHECK','UK','SERVICE/DB_POLICY'},'Unexpected owner constraint')
                continue
        if c['table']=='fems.meter_channel' and c['reason']=='관측 이력 보호':
            c['expression']='관측값 또는 배분 결과가 있는 채널의 에너지원·측정 종류·단위 변경 거부. 새 채널로 대체한다'
            c['columns']=['energy_source_id','measurement_kind','unit']
        kept.append(c)
    d['constraints']=kept
    reading=[r for r in d['relations'] if r['source']=='fems.energy_reading' and r['target']=='fems.meter_channel']
    need(len(reading)==1 and reading[0]['target_columns']==oldkey,'Unexpected reading FK')
    reading[0].update(columns=S+['meter_channel_id','unit'],target_columns=newkey,note='FS-008b: 같은 범위·채널·단위 일치; RESTRICT')

    allocation='fems.energy_allocation'
    field(allocation,'kwh').update(name='quantity',label='배분 에너지량',rule='채널 고유 단위의 비음수 배분량; 환산량이 아니다')
    tables[allocation]['columns'].insert(7,col('unit','배분 단위','varchar(10)',rule='meter_channel.unit과 동일; 단위 포함 복합 FK로 강제'))
    field(allocation,'equipment_id')['rule']='FEMS 내부 설비를 배분 기본 축으로 필수 참조'
    kwh_checks=[c for c in d['constraints'] if c['table']==allocation and c['expression']=='kwh >= 0']
    need(len(kwh_checks)==1,'Unexpected kwh CHECK')
    kwh_checks[0].update(columns=['quantity'],expression='quantity >= 0')
    allocfk=next(r for r in d['relations'] if r['source']==allocation and r['target']=='fems.meter_channel')
    allocfk.update(columns=S+['meter_channel_id','unit'],target_columns=newkey,note='FS-008b: 배분 결과와 채널 단위 일치')
    next(c for c in d['constraints'] if c['table']==allocation and c['kind']=='INDEX')['columns']=S+['meter_channel_id','unit']
    policy(allocation,['meter_channel_id','quantity','unit'],
           '기간 배분은 CUMULATIVE 채널만 허용하며 quantity는 채널 원단위, unit=meter_channel.unit이다. 전력 kWh, 가스 Nm3, 용수 m3를 서로 직접 합산하지 않는다. kW 순간 채널은 기간 배분 대상이 아니다. PRIMARY 환산 후에만 에너지원 간 합산하며 EMISSION은 배출량 계산에만 사용한다. 산정 결과는 불변이며 재산정은 새 method_version으로 생성한다','다중 에너지원 배분 단위')

    item='erp.item'
    tables[item]['columns'].append(col('tax_category','과세구분','varchar(20)',rule='TAXABLE 과세(상수 10%) / ZERO 영세(0%) / EXEMPT 면세(0%); 명시 선택'))
    constraint(item,'CHECK',['tax_category'],"tax_category IN ('TAXABLE','ZERO','EXEMPT')",'과세구분 3종 제한')
    d['code_lists'].append(dict(target=item,column='tax_category',values=['TAXABLE','ZERO','EXEMPT'],default=None,note='과세 10%, 영세 0%, 면세 0%. 세율 마스터 없음'))
    policy(item,['tax_category'],'부가세율 10%는 상수이며 세율 마스터가 없다. 영세와 면세는 각각 별도 구분이고 계산 세율은 0%. 거래 금액 확정 시 해당 품목 구분으로 세액을 계산하며 확정 금액은 품목 변경으로 재계산하지 않는다','고정 세율 출처')
    for t in ['erp.sales_record','erp.purchase_invoice_line']:
        policy(t,['supply_amount','tax_amount'],
               '연결된 거래 명세의 ERP 품목 과세구분을 확정 트랜잭션에서 읽어 TAXABLE 10%, ZERO/EXEMPT 0%를 적용한다. 공급가액은 세액 별도 금액이며 명세별 공급가액×세율을 KRW 1원 단위 사사오입한 뒤 세액을 합산한다. 매출은 출하 명세→출하지시 명세→수주 명세의 품목을 따른다. 매입은 해당 매입 명세 품목을 따른다. 합계와 대조 후 확정하고 이후 마스터 변경으로 확정 금액을 재산정하지 않는다','FS-008b 세액 계산 정책')

    partner='erp.partner'
    tables[partner]['columns'].append(col('payment_term_days','기준일 후 결제일수','integer',True,rule='NULL 미설정 / 0 당일 / N일 후; 과거 확정 만기에 소급하지 않음'))
    constraint(partner,'CHECK',['payment_term_days'],'payment_term_days >= 0','NULL 허용, 지정 시 음수 금지')
    aging='NULL은 연령분석에서 만기 미설정 그룹으로 분리하고 연체로 분류하지 않는다. 확정 후 만기 불변; 이후 거래처 결제조건 변경·추가를 소급하지 않는다.'
    field('erp.receivable','due_date')['rule']='nullable. 매출 인식일(Asia/Seoul)+결제일수 스냅샷; 조건 미설정이면 NULL. 수기 입력 금지'
    policy('erp.receivable',['sales_record_id','due_date'],
           '매출 확정 트랜잭션에서 거래처 조건을 일관되게 읽어 recognized_at의 Asia/Seoul 날짜+payment_term_days로 산출한다. 조건 NULL이면 due_date=NULL로 채권을 생성하며 매출 확정을 막지 않는다. 수기 만기 입력 경로 없음. '+aging,'FS-008b 채권 만기 스냅샷')
    field('erp.purchase_invoice','due_date')['rule']='draft 수기 우선. 확정 시 미입력이면 매입일+거래처 결제일수; 조건도 없으면 NULL. 확정 후 불변'
    field('erp.payable','due_date')['rule']='nullable. 매입 확정 시 purchase_invoice.due_date를 복사한 불변 스냅샷'
    policy('erp.purchase_invoice',['invoice_date','due_date','status'],
           'draft에서 직접 입력한 due_date가 최우선이다. 비어 있으면 확정 트랜잭션에서 invoice_date+partner.payment_term_days로 산출한다. 조건도 NULL이면 NULL을 유지하며 확정을 막지 않는다. 확정 결과를 payable.due_date에 복사한다. 확정 후 invoice_date·due_date 변경 금지. '+aging,'FS-008b 매입 만기 우선순위')
    policy('erp.payable',['purchase_invoice_id','due_date'],
           '매입 확정과 같은 트랜잭션에서 purchase_invoice.due_date를 NULL 포함 그대로 복사한다. 채무 자체 수기 변경 경로 없음. '+aging,'FS-008b 채무 만기 스냅샷')

    # Delete all owned metadata; reject an unexpected inbound reference rather than silently dropping it.
    deleted='core.dashboard_layout'
    need(not any(r['target']==deleted for r in d['relations']),'Unexpected inbound dashboard FK')
    d['tables']=[t for t in d['tables'] if t['name']!=deleted]
    d['relations']=[r for r in d['relations'] if r['source']!=deleted]
    d['constraints']=[c for c in d['constraints'] if c['table']!=deleted]
    d['states']=[s for s in d['states'] if s['table']!=deleted]
    d['code_lists']=[c for c in d['code_lists'] if c['target']!=deleted]

    policy('mes.operation_execution',['equipment_id','ended_at'],
           '시작 시 공간→세대→작업지시→LOT→실행의 기존 잠금 순서를 따른다. 동일 S의 공간 행 잠금으로 해당 설비의 모든 실행 시작·종료·설비 변경을 직렬화하고 잠금 획득 후 같은 equipment_id의 ended_at IS NULL 실행이 있으면 시작을 거부한다. 동시 시작 검사와 INSERT는 같은 트랜잭션이며 실패 시 전체 롤백. 공간 잠금 완화 전에는 설비별 직렬화 계약을 별도 설계해야 한다. 직접 DB 쓰기는 보호하지 않는다','FS-008b 설비 동시 점유 방지')
    packing=next(c for c in d['constraints'] if c['table']=='mes.packing_member' and c['reason']=='TX-10 양품 초과 패킹 거부')
    packing['expression']='공간→세대→작업지시→LOT(id 오름차순)→패킹 단위→구성 순서로 잠근다. 잠금 후 해당 LOT의 최종 확정 양품수량과 최신 SUM(packing_member.packed_qty)를 다시 조회한다. 추가·변경 결과 합계가 양품수량을 초과하면 전체 롤백한다. 구성 삭제도 같은 잠금 규칙을 사용한다. 팔레트 포장 때문에 BOX 구성을 다시 합산하지 않는다. 동일 트랜잭션으로 감사·요청 결과를 기록한다. 여러 행 합계이므로 일반 CHECK로 표현할 수 없고 직접 DB 쓰기는 보호하지 않는다'
    packing['columns']=['lot_id','packed_qty']
    for c in d['constraints']:
        if c['table']=='core.workspace' and c['reason']=='AC-48 / AC-49':
            c['expression']='expires_at 도달만으로 작업 중 세션을 종료하거나 공간을 회수하지 않는다. 세션 종료 및 진행 중 요청 없음 확인 후 TX-12 회수 대상이 된다. guest_pool→공간 잠금 안에서 만료·세션 종료·진행 요청 부재를 다시 확인하고 자식→부모 순 삭제 및 core.job_run 기록을 수행한다. 실패는 공간 단위로 기록한다. 신규 세션으로 만료 공간을 재개하지 않는다. 세션 생존·종료 판정은 서비스 책임이며 브라우저 종료 이벤트만으로 단정하지 않는다. DB 제약이 아니다'
    d.update(version='0.9.0',task='FS-008b',date='2026-09-22',basis='FS-013 + FS-008a 화면 갭 + FS-008b 사용자 확정 결정')
    d['sources'].append('FS-008b 화면 설계 반영 스키마 수정')
    d['change_log'].append(dict(version='0.9.0',task='FS-008b',date='2026-09-22',change='dashboard_layout 삭제, 배분 quantity/unit, owner_module 3개 제거·단위 FK 유지, 과세구분·nullable 만기 스냅샷·SERVICE 정책. 71테이블',status='정적 메타데이터 검증 대상 / DB·서비스 미적용'))
    need(counts(d)==AFTER,'Output count mismatch')
    check(d,'FS-008b')
    return d


import argparse
import hashlib
import os
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schema',type=Path,default=ROOT/'docs/db/schema-metadata/schema.json')
    parser.add_argument('--backup-dir',type=Path)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    try:
        raw=args.schema.read_bytes();d=json.loads(raw)
        need(d.get('migration_revision') is None,'DB-applied metadata is out of scope')
        if d.get('version')=='0.9.0' and d.get('task')=='FS-008b':
            need(counts(d)==AFTER,'Invalid applied counts');check(d,'FS-008b')
            print('FS-008b already applied and valid; no files changed.');return 0
        result=transform(d)
        payload=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
        if args.check:
            print(json.dumps(dict(check='passed',tables=counts(result),total=len(result['tables']),written=False)));return 0
        need(args.schema.read_bytes()==raw,'Source changed during validation')
        backup_dir=args.backup_dir or args.schema.parent/'backups';backup_dir.mkdir(parents=True,exist_ok=True)
        backup=backup_dir/f'schema.before-FS-008b.{hashlib.sha256(raw).hexdigest()}.json'
        if backup.exists():need(backup.read_bytes()==raw,'Existing backup content mismatch')
        else:
            with backup.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(dir=args.schema.parent,prefix='.fs008b-',delete=False) as f:
                temporary=Path(f.name);f.write(payload);f.flush();os.fsync(f.fileno())
            temporary.chmod(args.schema.stat().st_mode & 0o777)
            need(args.schema.read_bytes()==raw,'Source changed before replacement')
            os.replace(temporary,args.schema)
        finally:
            if temporary and temporary.exists():temporary.unlink()
        print(json.dumps(dict(applied='FS-008b',tables=counts(result),total=len(result['tables']),backup=str(backup)),ensure_ascii=False,indent=2))
        return 0
    except (OSError,ValueError,KeyError,TypeError,StopIteration) as exc:
        print(f'ABORT: {exc}');return 1


if __name__=='__main__':
    raise SystemExit(main())

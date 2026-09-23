"""FS-005c(FEMS 다중 에너지원)를 schema.json v0.3.0에 반영한다.

재실행 가능하다. 이미 적용된 상태에서 다시 실행하면 아무것도 바꾸지 않는다.
DB에 접속하지 않으며 메타데이터만 수정한다.

실행: python3 tools/apply_fs005c.py
이후 반드시 아래를 차례로 실행한다.
  npm run db:validate
  npm run db:build
  python3 tools/build_erd.py        (ERD 재생성)
  python3 tools/add_db_links.py     (Excel 내부 링크)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / 'docs/db/schema-metadata/schema.json'

d = json.loads(SCHEMA.read_text())
tables = {t['name']: t for t in d['tables']}

if 'core.energy_source' in tables:
    print('FS-005c already applied; nothing to do.')
    raise SystemExit(0)

# ── 전제 검사. 구조가 예상과 다르면 추측하지 않고 중단한다.
for need in ['core.meter', 'fems.energy_reading', 'fems.energy_allocation', 'bems.energy_reading']:
    if need not in tables:
        raise SystemExit(f'ABORT: {need} 가 없다. 메타데이터 버전을 확인하라.')

meter = tables['core.meter']
mcols = {c['name']: c for c in meter['columns']}
for need in ['measurement_kind', 'unit', 'owner_module']:
    if need not in mcols:
        raise SystemExit(f'ABORT: core.meter 에 {need} 컬럼이 없다. 이미 구조가 바뀐 상태일 수 있다.')

READING_TABLES = ['fems.energy_reading', 'fems.energy_allocation', 'bems.energy_reading']
for t in READING_TABLES:
    if not any(c['name'] == 'meter_id' for c in tables[t]['columns']):
        raise SystemExit(f'ABORT: {t} 에 meter_id 컬럼이 없다.')

# ── 공통 컬럼 템플릿을 기존 테이블에서 복사한다. 추측하지 않는다.
SCOPE = [dict(mcols['workspace_id']), dict(mcols['generation_id'])]
ID_COL = dict(mcols['id'])
CREATED = next((dict(c) for c in meter['columns'] if c['name'] == 'created_at'), None)
if CREATED is None:
    raise SystemExit('ABORT: core.meter 에 created_at 이 없다.')

anchor = [r for r in d['relations']
          if r['source'] == 'core.meter' and set(r['columns']) == {'workspace_id', 'generation_id'}]
if not anchor:
    raise SystemExit('ABORT: core.meter 의 범위 앵커 FK를 찾지 못했다.')

new_tables, new_constraints, new_relations = [], [], []


def col(name, label, type_, nullable=False, default=None, rule=''):
    return dict(name=name, label=label, type=type_, nullable=nullable, default=default, rule=rule)


def add(name, label, note, body, retention='세대 교체'):
    cols = [dict(ID_COL)] + [dict(x) for x in SCOPE] + body + [dict(CREATED)]
    new_tables.append(dict(name=name, label=label, scope='generation', phase='M2',
                           retention=retention, note=note, columns=cols))
    new_constraints.append(dict(table=name, kind='PK', columns=['id'], expression='', reason='기본키'))
    new_constraints.append(dict(table=name, kind='UK', columns=['workspace_id', 'generation_id', 'id'],
                                expression='', reason='공간·세대 복합 참조 대상'))
    for r in anchor:
        new_relations.append(dict(r, source=name))


def uk(table, columns, reason):
    new_constraints.append(dict(table=table, kind='UK', columns=columns, expression='', reason=reason))


def chk(table, columns, expression, reason):
    new_constraints.append(dict(table=table, kind='CHECK', columns=columns,
                                expression=expression, reason=reason))


def pol(table, columns, expression, reason):
    new_constraints.append(dict(table=table, kind='SERVICE/DB_POLICY', columns=columns,
                                expression=expression, reason=reason))


def fk(source, cols, target, tcols, note):
    new_relations.append(dict(source=source, columns=['workspace_id', 'generation_id'] + cols,
                              target=target, target_columns=['workspace_id', 'generation_id'] + tcols,
                              on_delete='RESTRICT', on_update='RESTRICT', note=note))


# ────────────────────────────── 신규 테이블 ──────────────────────────────
add('core.energy_source', '에너지원', 'FS-005c 3장. 전력·가스·용수를 동일 구조로 관리', [
    col('source_code', '에너지원 코드', 'varchar(20)', rule='ELEC / GAS / WATER / STEAM / AIR'),
    col('name', '에너지원명', 'varchar(50)'),
    col('source_kind', '에너지 구분', 'varchar(20)', rule='ELECTRIC / FUEL / HEAT / UTILITY'),
    col('measure_unit', '계측 단위', 'varchar(10)', rule='kWh / Nm3 / m3 / ton'),
    col('is_billable', '요금 부과 대상', 'boolean', default='true',
        rule='사내 생산 유틸리티는 false'),
    col('is_active', '사용 여부', 'boolean', default='true'),
])
uk('core.energy_source', ['workspace_id', 'generation_id', 'source_code'], '세대 내 코드 유일')
chk('core.energy_source', ['source_kind'],
    "source_kind IN ('ELECTRIC','FUEL','HEAT','UTILITY')", '에너지 구분 제한')

add('core.meter_channel', '계측 채널', 'FS-005c 3장. 계측기 1대가 여러 항목을 측정한다', [
    col('meter_id', '계측기', 'bigint'),
    col('energy_source_id', '에너지원', 'bigint'),
    col('channel_code', '채널 코드', 'varchar(20)'),
    col('name', '채널명', 'varchar(50)'),
    col('measurement_kind', '측정 종류', 'varchar(20)',
        rule='CUMULATIVE / INSTANT. 기간 합계는 CUMULATIVE만'),
    col('unit', '채널 단위', 'varchar(10)', rule='에너지원 단위와 다를 수 있다(kW vs kWh)'),
    col('owner_module', '관측 소유 모듈', 'varchar(20)',
        rule='소속 계측기의 owner_module 과 일치해야 한다'),
    col('multiplier', '계기 배수', 'numeric(18,6)', default='1'),
    col('is_active', '사용 여부', 'boolean', default='true'),
])
uk('core.meter_channel', ['workspace_id', 'generation_id', 'meter_id', 'channel_code'], '계측기 내 채널 유일')
uk('core.meter_channel', ['workspace_id', 'generation_id', 'id', 'owner_module', 'unit'],
   '관측값의 소유 모듈·단위 일치 강제용 참조 대상')
chk('core.meter_channel', ['measurement_kind'],
    "measurement_kind IN ('CUMULATIVE','INSTANT')", '측정 종류 제한')
chk('core.meter_channel', ['multiplier'], 'multiplier > 0', '배수는 양수')
pol('core.meter_channel', ['owner_module'],
    '채널의 owner_module 은 소속 계측기의 owner_module 과 같아야 한다', '모듈 소유 경계 유지')
pol('core.meter_channel', ['measurement_kind'],
    '관측값이 있는 채널의 에너지원·측정 종류·소유 모듈 변경 거부. 새 채널로 대체한다', '관측 이력 보호')
pol('core.meter_channel', ['measurement_kind'],
    '기간 합계는 measurement_kind = CUMULATIVE 채널만 대상으로 한다', 'kW와 kWh 혼합 차단')
fk('core.meter_channel', ['meter_id'], 'core.meter', ['id'], '소속 계측기')
fk('core.meter_channel', ['energy_source_id'], 'core.energy_source', ['id'], '측정 대상 에너지원')

add('fems.energy_factor', '환산·배출 계수', 'FS-005c 3장. 환산과 배출을 한 구조로 관리', [
    col('energy_source_id', '에너지원', 'bigint'),
    col('factor_kind', '계수 유형', 'varchar(20)',
        rule='PRIMARY:1차에너지 환산 / EMISSION:탄소 배출'),
    col('effective_year', '적용 연도', 'varchar(4)', rule="'YYYY'. 연도는 정수가 아닌 문자"),
    col('factor_value', '계수값', 'numeric(18,6)'),
    col('factor_unit', '계수 단위', 'varchar(20)', rule='TOE/단위, tCO2eq/단위'),
    col('source_note', '계수 출처', 'varchar(200)'),
], retention='세대 교체')
uk('fems.energy_factor',
   ['workspace_id', 'generation_id', 'energy_source_id', 'factor_kind', 'effective_year'],
   '에너지원·유형·연도별 1건')
chk('fems.energy_factor', ['factor_kind'],
    "factor_kind IN ('PRIMARY','EMISSION')", '계수 유형 제한')
chk('fems.energy_factor', ['effective_year'], "effective_year ~ '^[0-9]{4}$'", '연도 형식 강제')
chk('fems.energy_factor', ['factor_value'], 'factor_value > 0', '계수는 양수')
pol('fems.energy_factor', ['factor_kind'],
    'PRIMARY 는 에너지원 간 합산용, EMISSION 은 배출량 산정용이다. 환산값에 배출계수를 곱하지 않는다',
    '계수 오용 차단')
pol('fems.energy_factor', ['effective_year'],
    '적용 연도의 계수가 없으면 추정으로 대체하지 않고 계산 불가로 표시한다', '근거 없는 수치 차단')
fk('fems.energy_factor', ['energy_source_id'], 'core.energy_source', ['id'], '대상 에너지원')

add('fems.tariff', '요금제', 'FS-005c 3장. 단일요금제. 시간대 차등 없음', [
    col('energy_source_id', '에너지원', 'bigint'),
    col('tariff_code', '요금제 코드', 'varchar(30)'),
    col('name', '요금제명', 'varchar(100)'),
    col('contract_type', '계약 종별', 'varchar(50)', nullable=True),
    col('basic_charge', '기본요금 단가', 'numeric(18,4)', default='0'),
    col('usage_rate', '사용량 단가', 'numeric(18,4)'),
    col('currency', '통화', 'varchar(3)', default="'KRW'"),
    col('effective_from', '적용 시작 연월', 'varchar(7)', rule="'YYYY-MM'"),
    col('effective_to', '적용 종료 연월', 'varchar(7)', nullable=True,
        rule="'YYYY-MM'. NULL이면 현재 적용 중"),
])
uk('fems.tariff', ['workspace_id', 'generation_id', 'energy_source_id', 'tariff_code', 'effective_from'],
   '에너지원·요금제·적용 시작별 1건')
chk('fems.tariff', ['effective_from'], "effective_from ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'", '연월 형식 강제')
chk('fems.tariff', ['usage_rate'], 'usage_rate >= 0', '음수 단가 차단')
pol('fems.tariff', ['usage_rate'],
    '요금 = 기본요금 + (사용량 x 사용량 단가). 시간대 가중치를 적용하지 않는다', '단일요금제 전제')
fk('fems.tariff', ['energy_source_id'], 'core.energy_source', ['id'], '대상 에너지원')

add('fems.energy_target', '에너지 목표', 'FS-005c 3장', [
    col('site_id', '사업장', 'bigint', nullable=True),
    col('equipment_id', '설비', 'bigint', nullable=True),
    col('energy_source_id', '에너지원', 'bigint', nullable=True,
        rule='NULL이면 환산 기준 전체 에너지 목표'),
    col('target_scope', '적용 범위', 'varchar(20)', rule='SITE / EQUIPMENT'),
    col('target_month', '목표 연월', 'varchar(7)', rule="'YYYY-MM'"),
    col('target_value', '목표값', 'numeric(18,6)'),
    col('unit', '단위', 'varchar(10)'),
])
uk('fems.energy_target',
   ['workspace_id', 'generation_id', 'target_scope', 'site_id', 'equipment_id',
    'energy_source_id', 'target_month'], '범위·대상·에너지원·연월별 1건')
chk('fems.energy_target', ['target_scope'],
    "target_scope IN ('SITE','EQUIPMENT')", '적용 범위 제한')
chk('fems.energy_target', ['target_scope', 'site_id', 'equipment_id'],
    "(target_scope = 'SITE' AND site_id IS NOT NULL AND equipment_id IS NULL) OR "
    "(target_scope = 'EQUIPMENT' AND equipment_id IS NOT NULL)", '범위별 대상 강제')
chk('fems.energy_target', ['target_month'],
    "target_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'", '연월 형식 강제')
fk('fems.energy_target', ['site_id'], 'core.site', ['id'], '대상 사업장')
fk('fems.energy_target', ['equipment_id'], 'core.equipment', ['id'], '대상 설비')
fk('fems.energy_target', ['energy_source_id'], 'core.energy_source', ['id'], '대상 에너지원')

add('fems.energy_baseline', '원단위 기준선', 'FS-005c 3장', [
    col('baseline_code', '기준선 코드', 'varchar(30)'),
    col('baseline_scope', '적용 범위', 'varchar(20)', rule='ITEM / EQUIPMENT'),
    col('item_id', '품목', 'bigint', nullable=True),
    col('equipment_id', '설비', 'bigint', nullable=True),
    col('energy_source_id', '에너지원', 'bigint', nullable=True,
        rule='NULL이면 1차에너지 환산 기준'),
    col('baseline_value', '기준 원단위', 'numeric(18,6)', rule='생산 단위당 에너지'),
    col('unit', '원단위 단위', 'varchar(20)', rule='kWh/EA, TOE/ton 등'),
    col('period_from', '산정 시작 연월', 'varchar(7)', rule="'YYYY-MM'"),
    col('period_to', '산정 종료 연월', 'varchar(7)', rule="'YYYY-MM'"),
    col('status', '상태', 'varchar(20)', default="'draft'", rule='draft / confirmed'),
])
uk('fems.energy_baseline', ['workspace_id', 'generation_id', 'baseline_code'], '세대 내 코드 유일')
chk('fems.energy_baseline', ['baseline_scope'],
    "baseline_scope IN ('ITEM','EQUIPMENT')", '적용 범위 제한')
chk('fems.energy_baseline', ['baseline_scope', 'item_id', 'equipment_id'],
    "(baseline_scope = 'ITEM' AND item_id IS NOT NULL AND equipment_id IS NULL) OR "
    "(baseline_scope = 'EQUIPMENT' AND equipment_id IS NOT NULL AND item_id IS NULL)",
    '범위별 대상 강제')
chk('fems.energy_baseline', ['baseline_value'], 'baseline_value > 0', '기준 원단위는 양수')
pol('fems.energy_baseline', ['baseline_value'],
    '원단위 = 환산 에너지 / 생산량. 생산량이 0이면 계산 불가로 표시하고 0으로 기록하지 않는다',
    '분모 0 처리')
pol('fems.energy_baseline', ['status'], 'confirmed 이후 값 변경 거부', '확정 기준선 보호')
fk('fems.energy_baseline', ['item_id'], 'core.item', ['id'], '대상 품목')
fk('fems.energy_baseline', ['equipment_id'], 'core.equipment', ['id'], '대상 설비')
fk('fems.energy_baseline', ['energy_source_id'], 'core.energy_source', ['id'], '대상 에너지원')

# ────────────────────── 기존 테이블 구조 변경 ──────────────────────
# 1) core.meter 에서 측정 종류·단위를 제거한다. 계측기는 물리 장비, 채널이 측정 항목이다.
DROP = {'measurement_kind', 'unit'}
meter['columns'] = [c for c in meter['columns'] if c['name'] not in DROP]
removed_c, kept_c = [], []
for c in d['constraints']:
    if c['table'] == 'core.meter' and set(c['columns']) & DROP:
        shrunk = [x for x in c['columns'] if x not in DROP]
        if c['kind'] in ('PK', 'UK') and shrunk:
            kept_c.append(dict(c, columns=shrunk,
                               reason=c['reason'] + ' (FS-005c: 측정 종류·단위는 채널로 이동)'))
        else:
            removed_c.append(c)
    else:
        kept_c.append(c)
d['constraints'] = kept_c

# 2) 관측 테이블 3종의 참조를 계측기에서 채널로 옮긴다.
rewired = []
for tname in READING_TABLES:
    t = tables[tname]
    for c in t['columns']:
        if c['name'] == 'meter_id':
            c['name'] = 'meter_channel_id'
            c['label'] = '계측 채널'
            c['rule'] = 'FS-005c: 계측기가 아니라 채널을 참조한다'
    for c in d['constraints']:
        if c['table'] == tname and 'meter_id' in c['columns']:
            c['columns'] = ['meter_channel_id' if x == 'meter_id' else x for x in c['columns']]
    for r in d['relations']:
        if r['source'] == tname:
            if 'meter_id' in r['columns']:
                r['columns'] = ['meter_channel_id' if x == 'meter_id' else x for x in r['columns']]
            if r['target'] == 'core.meter':
                r['target'] = 'core.meter_channel'
                r['note'] = (r.get('note') or '') + ' (FS-005c: 채널 참조로 전환)'
                rewired.append((tname, r['target_columns']))

# 3) 채널 쪽에 위 FK가 요구하는 고유키가 있는지 확인하고 없으면 추가한다.
have = {(c['table'], tuple(c['columns'])) for c in d['constraints'] + new_constraints
        if c['kind'] in ('PK', 'UK')}
for tname, tcols in rewired:
    key = ('core.meter_channel', tuple(tcols))
    if key not in have:
        new_constraints.append(dict(table='core.meter_channel', kind='UK', columns=list(tcols),
                                    expression='', reason=f'{tname} 참조 대상 (FS-005c)'))
        have.add(key)

# ────────────────────────────── 병합 ──────────────────────────────
d['tables'] += new_tables
d['constraints'] += new_constraints
d['relations'] += new_relations
d['version'] = '0.4.0'
d['task'] = 'FS-005d'
d['basis'] = d.get('basis', '') + ' · FS-005c'
d['states'] = d.get('states', []) + [
    dict(table='fems.energy_baseline', column='status', values=['draft', 'confirmed'],
         default='draft', transition='draft→confirmed; 확정 후 값 변경 금지'),
]
d['code_lists'] = d.get('code_lists', []) + [
    dict(target='core.energy_source', column='source_kind',
         values=['ELECTRIC', 'FUEL', 'HEAT', 'UTILITY'], default=None,
         note='전력 / 연료 / 열 / 유틸리티'),
    dict(target='core.meter_channel', column='measurement_kind',
         values=['CUMULATIVE', 'INSTANT'], default=None,
         note='기간 합계는 CUMULATIVE 채널만 대상으로 한다'),
    dict(target='fems.energy_factor', column='factor_kind',
         values=['PRIMARY', 'EMISSION'], default=None,
         note='PRIMARY 는 에너지원 간 합산용, EMISSION 은 배출량 산정용'),
]
d['change_log'] = d.get('change_log', []) + [
    dict(version='0.4.0', task='FS-005d', date='2026-09-21',
         change='FS-005c 반영: core 2개(energy_source, meter_channel), fems 4개(energy_factor, tariff, energy_target, energy_baseline) 추가',
         status='정적 검증; DB 미적용'),
    dict(version='0.4.0', task='FS-005d', date='2026-09-21',
         change='core.meter 에서 measurement_kind·unit 제거. 관측 3종(fems.energy_reading, fems.energy_allocation, bems.energy_reading)의 참조를 계측 채널로 전환',
         status='되돌리기 비싼 구조 변경. 물리 DDL 전 적용'),
]
d['sources'] = d.get('sources', []) + ['FS-005c FEMS 공통 설계 (다중 에너지원)']

SCHEMA.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(
    applied='FS-005c',
    added_tables=len(new_tables),
    added_constraints=len(new_constraints),
    added_relations=len(new_relations),
    removed_meter_constraints=len(removed_c),
    rewired_reading_tables=READING_TABLES,
    total_tables=len(d['tables']),
    total_columns=sum(len(t['columns']) for t in d['tables']),
    total_relations=len(d['relations']),
    next='npm run db:validate',
), ensure_ascii=False, indent=2))

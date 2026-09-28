"""FS-025a: BEMS 10테이블과 core.workspace_module 'bems'를 schema.json에 반영한다(멱등).

근거: docs/modules/bems/BEMS_모듈설계_FS-025.md 4장, docs/plan/BEMS도입_공용에너지_결정_FS-025.md.
FS-013 R4(bems 스키마 금지)는 FS-025 D18로 해제한다(audit_schema_isolation.FORBIDDEN).
이미 반영돼 있으면 아무것도 바꾸지 않는다. 새 제약·관계는 목록 끝에 붙여 기존 C·R 번호를 유지한다.
"""
import json
from pathlib import Path

from apply_fs023a import S, c, col, r, uk_partial
from apply_fs023a import table as _table

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / 'docs/db/schema-metadata/schema.json'
OLD_MODULE_CHECK = "module_key IN ('core','mes','erp','fems','qms','wms')"
NEW_MODULE_CHECK = "module_key IN ('core','mes','erp','fems','qms','wms','bems')"
CODE_FORMAT = "code ~ '^[A-Z][A-Z0-9-]{1,19}$'"
COMMANDS = ('POWER_ON', 'POWER_OFF', 'SET_MODE', 'SET_SETPOINT')
SETPOINTS = ('COOL_TEMP', 'HEAT_TEMP', 'CO2_MAX')


def quoted(values):
    return ', '.join(f"'{v}'" for v in values)


def table(name, label, sub, note, columns):
    return {**_table(name, label, sub, note, columns), 'phase': 'B1'}


def active():
    return col('is_active', '사용 여부', 'boolean', default='true')


TABLES = [
    table('bems.zone', '구역', 'bems_master', 'FS-025 4.1. BEMS 소유 구역(FS-013 D1). FEMS 공간과 연결되지 않는다', [
        col('code', '구역 코드', 'varchar(20)'),
        col('name', '구역명', 'varchar(100)'),
        col('kind', '구역 종류', 'varchar(12)', rule='OFFICE / PRODUCTION / UTILITY'),
        col('floor_area_m2', '바닥 면적', 'numeric(10,2)', nullable=True),
        active(),
    ]),
    table('bems.meter', '공용 계측기', 'bems_master', 'FS-025 4.1. 공용 전력 계측기. FEMS 계측기와 별개(D19)', [
        col('zone_id', '구역', 'bigint'),
        col('code', '계측기 코드', 'varchar(20)'),
        col('name', '계측기명', 'varchar(100)'),
        col('usage', '용도', 'varchar(10)', rule='LIGHTING / HVAC / OFFICE / OTHER. 등록 뒤 바꾸지 않는다'),
        col('unit', '단위', 'varchar(10)', default="'kWh'", rule='kWh 고정'),
        active(),
    ]),
    table('bems.sensor', '환경 센서', 'bems_master', 'FS-025 4.1. 구역·항목당 1개(1차)', [
        col('zone_id', '구역', 'bigint'),
        col('code', '센서 코드', 'varchar(20)'),
        col('metric', '측정 항목', 'varchar(10)', rule='TEMP / HUMIDITY / CO2'),
        col('unit', '단위', 'varchar(10)', rule='항목과 일치: ℃ / % / ppm'),
        active(),
    ]),
    table('bems.hvac_unit', '공조기', 'bems_master', 'FS-025 4.1·D21. 모의 공조기. 상태는 제어 명령·스케줄 전환으로만 바뀐다', [
        col('zone_id', '구역', 'bigint'),
        col('code', '공조기 코드', 'varchar(20)'),
        col('name', '공조기명', 'varchar(100)'),
        col('meter_id', '공조 전력 계측기', 'bigint', nullable=True, rule='용도 HVAC 계측기만'),
        col('rated_kw', '정격 전력', 'numeric(8,2)'),
        col('state', '운전 상태', 'varchar(4)', default="'OFF'", rule='OFF / COOL / HEAT / FAN'),
        col('control_source', '운전 출처', 'varchar(10)', default="'SCHEDULE'", rule='SCHEDULE / MANUAL'),
        col('state_changed_at', '상태 변경 시각', 'timestamptz', nullable=True),
        active(),
    ]),
    table('bems.energy_reading', '공용 전력 관측', 'metering', 'FS-025 4.2. 1시간 구간 kWh. 불변', [
        col('meter_id', '공용 계측기', 'bigint'),
        col('period_start', '구간 시작', 'timestamptz', rule='정시. 구간 [시작, 시작+1h)'),
        col('value', '전력량', 'numeric(12,3)'),
        col('quality', '품질', 'varchar(10)', default="'valid'", rule='valid / invalid'),
        col('source', '출처', 'varchar(12)', rule='SEED / SIMULATION'),
    ]),
    table('bems.environment_reading', '환경 관측', 'metering', 'FS-025 4.2. 1시간 구간 평균. 불변', [
        col('sensor_id', '환경 센서', 'bigint'),
        col('period_start', '구간 시작', 'timestamptz', rule='정시'),
        col('value', '관측값', 'numeric(8,2)'),
        col('quality', '품질', 'varchar(10)', default="'valid'", rule='valid / invalid'),
        col('source', '출처', 'varchar(12)', rule='SEED / SIMULATION'),
    ]),
    table('bems.schedule_slot', '운전 스케줄', 'hvac', 'FS-025 4.3. 공조기별 평일·주말 시간대. 겹침 거부', [
        col('hvac_unit_id', '공조기', 'bigint'),
        col('day_kind', '요일 구분', 'varchar(8)', rule='WEEKDAY / WEEKEND'),
        col('start_hour', '시작 시', 'integer', rule='0~23'),
        col('end_hour', '종료 시', 'integer', rule='1~24, 시작보다 크다'),
        col('mode', '운전 모드', 'varchar(4)', rule='COOL / HEAT / FAN'),
        active(),
    ]),
    table('bems.control_command', '제어 명령', 'hvac', 'FS-025 4.3. 불변 이력. 설정값 변경도 명령(현재 설정값 = 마지막 적용 명령)', [
        col('zone_id', '구역', 'bigint'),
        col('hvac_unit_id', '공조기', 'bigint', nullable=True, rule='설정값 변경은 구역 단위라 비울 수 있다'),
        col('command', '명령', 'varchar(14)', rule=' / '.join(COMMANDS)),
        col('mode', '모드', 'varchar(4)', nullable=True, rule='SET_MODE이면 필수'),
        col('setpoint_kind', '설정값 항목', 'varchar(10)', nullable=True, rule=' / '.join(SETPOINTS)),
        col('value', '설정값', 'numeric(8,2)', nullable=True),
        col('source', '출처', 'varchar(10)', rule='MANUAL / SCHEDULE / SEED'),
        col('requested_at', '요청 시각', 'timestamptz'),
        col('result', '결과', 'varchar(10)', rule='APPLIED / REJECTED'),
        col('reject_reason', '거부 사유', 'varchar(40)', nullable=True),
        col('note', '메모', 'varchar(300)', nullable=True),
    ]),
    table('bems.alarm_rule', '경보 규칙', 'alarm', 'FS-025 4.4. 구역·항목·비교당 1개', [
        col('zone_id', '구역', 'bigint'),
        col('metric', '측정 항목', 'varchar(10)', rule='TEMP / HUMIDITY / CO2'),
        col('comparator', '비교', 'varchar(4)', rule='HIGH / LOW'),
        col('threshold', '한계값', 'numeric(8,2)'),
        col('duration_hours', '지속 시간', 'integer', rule='1~24 연속 시간'),
        col('severity', '등급', 'varchar(10)', rule='WARNING / CRITICAL'),
        active(),
    ]),
    table('bems.alarm', '경보', 'alarm', 'FS-025 4.4·D22. 발생 → 확인 → 해제. 해제 후 불변', [
        col('alarm_rule_id', '경보 규칙', 'bigint'),
        col('sensor_id', '환경 센서', 'bigint'),
        col('status', '상태', 'varchar(14)', default="'raised'", rule='raised / acknowledged / cleared'),
        col('raised_at', '발생 시각', 'timestamptz'),
        col('peak_value', '최고(최저)값', 'numeric(8,2)'),
        col('acknowledged_at', '확인 시각', 'timestamptz', nullable=True),
        col('ack_note', '확인 메모', 'varchar(300)', nullable=True),
        col('cleared_at', '해제 시각', 'timestamptz', nullable=True),
    ]),
]
ZN, MT, SN, HU, ER, EV, SS, CC, AR, AL = (t['name'] for t in TABLES)

CONSTRAINTS = []
for t in TABLES:
    CONSTRAINTS += [c(t['name'], 'PK', ['id'], reason='기본키'),
                    c(t['name'], 'UK', S + ['id'], reason='공간·세대 복합 참조 대상')]
QUALITY = "quality IN ('valid', 'invalid')"
SOURCE = "source IN ('SEED', 'SIMULATION')"
CONSTRAINTS += [
    c(ZN, 'UK', S + ['code'], reason='세대 내 구역 코드 유일'),
    c(ZN, 'CHECK', ['code'], CODE_FORMAT, '코드 형식'),
    c(ZN, 'CHECK', ['kind'], "kind IN ('OFFICE', 'PRODUCTION', 'UTILITY')", '구역 종류 값'),
    c(ZN, 'CHECK', ['floor_area_m2'], 'floor_area_m2 IS NULL OR floor_area_m2 > 0', '면적 양수'),
    c(ZN, 'SERVICE/DB_POLICY', ['id'], '계측기·센서·공조기가 있는 구역은 삭제를 거부하고 사용 안 함으로 바꾼다', '기준정보 보존'),
    c(MT, 'UK', S + ['code'], reason='세대 내 계측기 코드 유일'),
    c(MT, 'CHECK', ['code'], CODE_FORMAT, '코드 형식'),
    c(MT, 'CHECK', ['usage'], "usage IN ('LIGHTING', 'HVAC', 'OFFICE', 'OTHER')", '용도 값'),
    c(MT, 'CHECK', ['unit'], "unit = 'kWh'", '공용 전력은 kWh'),
    c(MT, 'SERVICE/DB_POLICY', ['usage'], '용도는 등록 뒤 바꾸지 않는다. 관측이 있는 계측기는 삭제 대신 사용 안 함', '분해 이력 보존'),
    c(SN, 'UK', S + ['code'], reason='세대 내 센서 코드 유일'),
    c(SN, 'UK', S + ['zone_id', 'metric'], reason='구역·항목당 센서 1개(1차)'),
    c(SN, 'CHECK', ['code'], CODE_FORMAT, '코드 형식'),
    c(SN, 'CHECK', ['metric', 'unit'],
      "(metric = 'TEMP' AND unit = '℃') OR (metric = 'HUMIDITY' AND unit = '%') OR (metric = 'CO2' AND unit = 'ppm')", '항목·단위 일치'),
    c(HU, 'UK', S + ['code'], reason='세대 내 공조기 코드 유일'),
    c(HU, 'CHECK', ['code'], CODE_FORMAT, '코드 형식'),
    c(HU, 'CHECK', ['rated_kw'], 'rated_kw > 0', '정격 양수'),
    c(HU, 'CHECK', ['state'], "state IN ('OFF', 'COOL', 'HEAT', 'FAN')", '운전 상태 값'),
    c(HU, 'CHECK', ['control_source'], "control_source IN ('SCHEDULE', 'MANUAL')", '운전 출처 값'),
    c(HU, 'SERVICE/DB_POLICY', ['meter_id'], '공조 전력 계측기는 같은 구역의 용도 HVAC 계측기만', '계측 연결'),
    c(HU, 'SERVICE/DB_POLICY', ['state'],
      '상태는 제어 명령(TX-B1)과 1시간 진행의 스케줄 경계 전환(TX-B2)으로만 바뀐다. 수동 명령은 다음 스케줄 경계까지 유지', '모의 공조기 상태(D21)'),
    c(ER, 'UK', S + ['meter_id', 'period_start'], reason='계측기·구간당 1건(진행 멱등)'),
    c(ER, 'CHECK', ['value'], 'value >= 0', '전력량 음수 금지'),
    c(ER, 'CHECK', ['quality'], QUALITY, '품질 값'),
    c(ER, 'CHECK', ['source'], SOURCE, '출처 값'),
    c(ER, 'SERVICE/DB_POLICY', ['period_start'], '정시 구간만. 관측은 수정·삭제하지 않는다(세대 정리 제외)', '관측 불변'),
    c(EV, 'UK', S + ['sensor_id', 'period_start'], reason='센서·구간당 1건(진행 멱등)'),
    c(EV, 'CHECK', ['quality'], QUALITY, '품질 값'),
    c(EV, 'CHECK', ['source'], SOURCE, '출처 값'),
    c(EV, 'SERVICE/DB_POLICY', ['period_start'], '정시 구간만. 관측은 수정·삭제하지 않는다(세대 정리 제외)', '관측 불변'),
    c(SS, 'CHECK', ['day_kind'], "day_kind IN ('WEEKDAY', 'WEEKEND')", '요일 구분 값'),
    c(SS, 'CHECK', ['start_hour', 'end_hour'], 'start_hour BETWEEN 0 AND 23 AND end_hour BETWEEN 1 AND 24 AND start_hour < end_hour', '시간대 범위'),
    c(SS, 'CHECK', ['mode'], "mode IN ('COOL', 'HEAT', 'FAN')", '운전 모드 값'),
    c(SS, 'SERVICE/DB_POLICY', ['start_hour'], '같은 공조기·요일 구분의 사용 중 시간대는 겹칠 수 없다', '스케줄 겹침 거부'),
    c(CC, 'CHECK', ['command'], f'command IN ({quoted(COMMANDS)})', '명령 값'),
    c(CC, 'CHECK', ['command', 'hvac_unit_id'], "command = 'SET_SETPOINT' OR hvac_unit_id IS NOT NULL", '설비 명령은 공조기 필수'),
    c(CC, 'CHECK', ['command', 'mode'],
      "(command = 'SET_MODE' AND mode IN ('COOL', 'HEAT', 'FAN')) OR (command <> 'SET_MODE' AND mode IS NULL)", '모드 명령만 모드'),
    c(CC, 'CHECK', ['command', 'setpoint_kind', 'value'],
      f"(command = 'SET_SETPOINT' AND setpoint_kind IN ({quoted(SETPOINTS)}) AND value IS NOT NULL) OR "
      "(command <> 'SET_SETPOINT' AND setpoint_kind IS NULL AND value IS NULL)", '설정값 명령만 항목·값'),
    c(CC, 'CHECK', ['source'], "source IN ('MANUAL', 'SCHEDULE', 'SEED')", '출처 값'),
    c(CC, 'CHECK', ['result', 'reject_reason'],
      "(result = 'APPLIED' AND reject_reason IS NULL) OR (result = 'REJECTED' AND reject_reason IS NOT NULL)", '거부는 사유 필수'),
    c(CC, 'SERVICE/DB_POLICY', ['command'],
      '명령은 불변 이력이다. 현재 설정값 = 구역·항목의 마지막 APPLIED 설정값 명령. 범위(냉방 20~30, 난방 16~24, 냉방 ≥ 난방+2, CO₂ 600~2000) 밖이면 REJECTED로 기록', '설정값·명령 이력'),
    c(AR, 'UK', S + ['zone_id', 'metric', 'comparator'], reason='구역·항목·비교당 규칙 1개'),
    c(AR, 'CHECK', ['metric'], "metric IN ('TEMP', 'HUMIDITY', 'CO2')", '항목 값'),
    c(AR, 'CHECK', ['comparator'], "comparator IN ('HIGH', 'LOW')", '비교 값'),
    c(AR, 'CHECK', ['duration_hours'], 'duration_hours BETWEEN 1 AND 24', '지속 시간 범위'),
    c(AR, 'CHECK', ['severity'], "severity IN ('WARNING', 'CRITICAL')", '등급 값'),
    c(AL, 'CHECK', ['status'], "status IN ('raised', 'acknowledged', 'cleared')", '상태 값'),
    c(AL, 'CHECK', ['status', 'acknowledged_at', 'cleared_at'],
      "(status = 'raised' AND acknowledged_at IS NULL AND cleared_at IS NULL) OR "
      "(status = 'acknowledged' AND acknowledged_at IS NOT NULL AND cleared_at IS NULL) OR "
      "(status = 'cleared' AND cleared_at IS NOT NULL)", '상태와 시각 일치'),
    uk_partial(AL, ['alarm_rule_id', 'sensor_id'], "status <> 'cleared'", '규칙·센서당 해제되지 않은 경보 1건'),
    c(AL, 'SERVICE/DB_POLICY', ['status'],
      '발생·해제는 관측값 평가(TX-B2)로만, 확인은 사람만(TX-B3). 해제된 경보는 수정·삭제하지 않는다', '경보 수명(D22)'),
    c(MT, 'INDEX', S + ['zone_id'], reason='FK 조회'),
    c(HU, 'INDEX', S + ['zone_id'], reason='FK 조회'),
    c(HU, 'INDEX', S + ['meter_id'], reason='FK 조회'),
    c(SS, 'INDEX', S + ['hvac_unit_id', 'day_kind'], reason='FK 조회·겹침 검사'),
    c(CC, 'INDEX', S + ['zone_id', 'setpoint_kind', 'requested_at'], reason='현재 설정값 조회'),
    c(CC, 'INDEX', S + ['hvac_unit_id'], reason='FK 조회'),
    c(AL, 'INDEX', S + ['alarm_rule_id'], reason='FK 조회'),
    c(AL, 'INDEX', S + ['sensor_id'], reason='FK 조회'),
    c(AL, 'INDEX', S + ['status'], reason='활성 경보 조회'),
]

RELATIONS = [dict(source=t['name'], columns=S, target='core.data_generation', target_columns=['workspace_id', 'id'],
                  on_delete='RESTRICT', on_update='RESTRICT', note='같은 참조 범위 유지') for t in TABLES]
RELATIONS += [
    r(MT, ['zone_id'], ZN, '계측기의 구역'),
    r(SN, ['zone_id'], ZN, '센서의 구역'),
    r(HU, ['zone_id'], ZN, '공조기의 구역'),
    r(HU, ['meter_id'], MT, '공조 전력 계측기'),
    r(ER, ['meter_id'], MT, '관측의 계측기'),
    r(EV, ['sensor_id'], SN, '관측의 센서'),
    r(SS, ['hvac_unit_id'], HU, '스케줄의 공조기'),
    r(CC, ['zone_id'], ZN, '명령의 구역'),
    r(CC, ['hvac_unit_id'], HU, '명령의 공조기'),
    r(AR, ['zone_id'], ZN, '규칙의 구역'),
    r(AL, ['alarm_rule_id'], AR, '경보의 규칙'),
    r(AL, ['sensor_id'], SN, '경보의 센서'),
]

STATES = [
    dict(table=AL, column='status', values=['raised', 'acknowledged', 'cleared'], default='raised',
         transition='raised→acknowledged→cleared 또는 raised→cleared; 해제 후 불변'),
    dict(table=HU, column='state', values=['OFF', 'COOL', 'HEAT', 'FAN'], default='OFF',
         transition='제어 명령·스케줄 경계 전환으로만 변경(D21)'),
]


def apply(d):
    """schema dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if ZN in {t['name'] for t in d['tables']}:
        return False
    d['tables'].extend(TABLES)
    d['constraints'].extend(CONSTRAINTS)
    d['relations'].extend(RELATIONS)
    d['states'].extend(STATES)
    for cst in d['constraints']:
        if cst['table'] == 'core.workspace_module' and cst['expression'] == OLD_MODULE_CHECK:
            cst['expression'] = NEW_MODULE_CHECK
    for code in d['code_lists']:
        if code['target'] == 'core.workspace_module' and code['column'] == 'module_key':
            code['values'] = ['core', 'mes', 'erp', 'fems', 'qms', 'wms', 'bems']
            code['note'] = 'QMS(FS-023)·WMS(FS-024)·BEMS(FS-025)는 구현 솔루션. SCM 설명 카드와 도움말은 정적 파일'
    d['code_lists'].extend([
        dict(target=ZN, column='kind', values=['OFFICE', 'PRODUCTION', 'UTILITY'], default=None, note='구역 종류'),
        dict(target=MT, column='usage', values=['LIGHTING', 'HVAC', 'OFFICE', 'OTHER'], default=None, note='공용 전력 용도(분해 열)'),
        dict(target=SN, column='metric', values=['TEMP', 'HUMIDITY', 'CO2'], default=None, note='℃ / % / ppm'),
        dict(target=CC, column='command', values=list(COMMANDS), default=None, note='설정값 변경도 명령(D21)'),
        dict(target=CC, column='setpoint_kind', values=list(SETPOINTS), default=None, note='냉방 온도 / 난방 온도 / CO₂ 상한'),
        dict(target=AR, column='severity', values=['WARNING', 'CRITICAL'], default=None, note='경보 등급'),
    ])
    d.update(version='0.12.0', task='FS-025a', date='2026-09-28', migration_revision='fs025a_bems')
    d['change_log'].append(dict(version='0.12.0', task='FS-025a', date='2026-09-28',
                                change='bems 스키마 10테이블(구역·공용 계측기·환경 센서·공조기·공용 전력 관측·환경 관측·운전 스케줄·제어 명령·경보 규칙·경보), '
                                       'core.workspace_module module_key에 bems 추가, FS-013 R4의 bems 금지 해제(FS-025 D18). 스키마 간 FK 0건',
                                status='마이그레이션 fs025a_bems 적용 대상'))
    return True


def main():
    d = json.loads(SCHEMA.read_text(encoding='utf-8'))
    changed = apply(d)
    if changed:
        SCHEMA.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(changed=changed, tables=len(d['tables']), constraints=len(d['constraints']),
                          relations=len(d['relations'])), ensure_ascii=False))


if __name__ == '__main__':
    main()

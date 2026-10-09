"""FS-030a GW metadata, append-only constraint/relation numbering; idempotent."""
import copy
import json
from pathlib import Path

from apply_fs023a import S, c, col, r, table

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / 'docs/db/schema-metadata/schema.json'
ROLES = "'STAFF','MANAGER','EXECUTIVE','BOARD_ADMIN'"


def f(name, type_='varchar(100)', nullable=False, default=None):
    return col(name, name, type_, nullable, default)


def snapshot(prefix):
    return [f(prefix+'_code', 'varchar(30)'), f(prefix+'_name', 'varchar(80)'),
            f(prefix+'_job_role', 'varchar(20)')]


def version():
    return f('version', 'integer', default='1')


def named():
    return [f('code', 'varchar(30)'), f('name', 'varchar(100)'),
            f('is_active', 'boolean', default='true'), version()]


def event(owner):
    return [f(owner+'_id', 'bigint'), f('event_seq', 'integer'), f('event_type', 'varchar(30)'),
            f('acting_person_id', 'bigint'), *snapshot('person'),
            f('actor_kind', 'varchar(10)'), f('actor_key', 'varchar(100)'),
            f('reason', 'varchar(500)', True), f(owner+'_version', 'integer')]


TABLES = [
    table('gw.person', '체험 담당자', 'gw_master', 'FS-030 D61: 합성 역할, 실제 계정 아님', [
        f('code', 'varchar(30)'), f('name', 'varchar(80)'), f('job_role', 'varchar(20)'),
        f('is_active', 'boolean', default='true'), version()]),
    table('gw.approval_route', '결재선', 'gw_master', '초안 선택 때 문서 단계로 복사', named()),
    table('gw.route_step', '결재선 단계', 'gw_master', '순차 1~3명', [
        f('route_id', 'bigint'), f('seq', 'smallint'), f('person_id', 'bigint')]),
    table('gw.approval_document', '결재 문서', 'approval', '상신 후 본문·스냅샷 불변, 정정은 새 문서', [
        f('serial', 'bigint'), f('document_no', 'varchar(40)'), f('previous_document_id', 'bigint', True),
        f('round_no', 'integer', default='1'), f('kind', 'varchar(20)'), f('title', 'varchar(200)'),
        f('body', 'text'), f('drafter_id', 'bigint'), *snapshot('drafter'), f('route_id', 'bigint'),
        f('route_code', 'varchar(30)'), f('route_name', 'varchar(100)'),
        f('status', 'varchar(20)', default="'DRAFT'"), version(), f('submission_order', 'bigint', True),
        f('current_step', 'smallint', True), f('submitted_at', 'timestamptz', True),
        f('closed_at', 'timestamptz', True), f('source_kind', 'varchar(30)', True),
        f('source_no', 'varchar(40)', True), f('source_snapshot', 'jsonb', True),
        f('source_digest', 'varchar(64)', True), f('source_status', 'varchar(20)', True),
        f('amount', 'numeric(18,2)', True), f('currency', 'varchar(3)', True)]),
    table('gw.approval_step', '문서 결재 단계', 'approval', '상신 뒤 담당자 스냅샷 불변·상태 단방향', [
        f('document_id', 'bigint'), f('seq', 'smallint'), f('person_id', 'bigint'), *snapshot('person'),
        f('status', 'varchar(20)', default="'WAITING'"), f('decision_reason', 'varchar(500)', True),
        f('decided_at', 'timestamptz', True)]),
    table('gw.approval_event', '결재 사건', 'approval', '추가 전용, 실제 주체와 합성 역할 구분', [
        *event('document'), f('step_seq', 'smallint', True)]),
    table('gw.board_post', '게시글', 'board', '게시 후 불변·정정/철회 이력 보존', [
        f('serial', 'bigint'), f('post_no', 'varchar(40)'), f('previous_post_id', 'bigint', True),
        f('board_kind', 'varchar(10)'), f('author_id', 'bigint'), *snapshot('author'),
        f('title', 'varchar(200)'), f('body', 'text'), f('status', 'varchar(20)', default="'DRAFT'"),
        version(), f('published_at', 'timestamptz', True), f('withdrawn_at', 'timestamptz', True),
        f('withdraw_reason', 'varchar(500)', True)]),
    table('gw.board_event', '게시 사건', 'board', '추가 전용', event('post')),
]
for t in TABLES:
    t['phase'] = 'G1'
    for field in t['columns']:
        if field['name'] == 'created_at':
            field['default'] = 'clock_timestamp()'

P, RT, RS, D, DS, DE, B, BE = [t['name'] for t in TABLES]
CONSTRAINTS = []


def rule(t, columns, expression, reason='FS-030 DB 정합성'):
    CONSTRAINTS.append(c(t, 'CHECK', columns.split(','), expression, reason))


def key(t, *columns):
    CONSTRAINTS.append(c(t, 'UK', S + list(columns), reason='동일 공간·세대 내 유일'))


for t in TABLES:
    name = t['name']
    CONSTRAINTS.extend([c(name, 'PK', ['id'], reason='기본키'),
                        c(name, 'UK', S+['id'], reason='범위 복합 참조')])
    fields = {f['name'] for f in t['columns']}
    if 'version' in fields:
        rule(name, 'version', 'version > 0')
    for field in ('code', 'name', 'title', 'body', 'actor_key', 'document_no', 'post_no'):
        if field in fields:
            rule(name, field, f'char_length(btrim({field})) BETWEEN 1 AND '+str(10000 if field == 'body' else {'code':30,'name':100,'title':200,'actor_key':100,'document_no':40,'post_no':40}[field]))
    for field in fields:
        if field.endswith('job_role'):
            rule(name, field, f'{field} IN ({ROLES})')
    if 'serial' in fields:
        rule(name, 'serial', 'serial > 0')
        key(name, 'serial')
    if 'code' in fields:
        key(name, 'code')
        rule(name, 'code', "code ~ '^[A-Z0-9][A-Z0-9-]{1,29}$'")

for t, owner in [(RS, 'route_id'), (DS, 'document_id')]:
    key(t, owner, 'seq')
    key(t, owner, 'person_id')
    rule(t, 'seq', 'seq BETWEEN 1 AND 3')
key(D, 'document_no')
key(D, 'previous_document_id')
key(D, 'submission_order')
rule(D, 'round_no', 'round_no > 0')
rule(D, 'previous_document_id,id', 'previous_document_id IS NULL OR previous_document_id <> id')
rule(D, 'kind', "kind IN ('GENERAL','ERP_PURCHASE')")
rule(D, 'current_step', 'current_step IS NULL OR current_step BETWEEN 1 AND 3')
rule(D, 'submission_order', 'submission_order IS NULL OR submission_order > 0')
rule(D, 'status,submitted_at,closed_at,submission_order,current_step',
     "(status='DRAFT' AND submitted_at IS NULL AND closed_at IS NULL AND submission_order IS NULL AND current_step IS NULL) OR "
     "(status='IN_REVIEW' AND submitted_at IS NOT NULL AND closed_at IS NULL AND submission_order IS NOT NULL AND current_step IS NOT NULL) OR "
     "(status IN ('APPROVED','REJECTED','WITHDRAWN') AND submitted_at IS NOT NULL AND closed_at IS NOT NULL AND submission_order IS NOT NULL AND current_step IS NULL)")
rule(D, 'kind,source_kind,source_no,source_snapshot,source_digest,source_status',
     "(kind='GENERAL' AND source_kind IS NULL AND source_no IS NULL AND source_snapshot IS NULL AND source_digest IS NULL AND source_status IS NULL) OR "
     "(kind='ERP_PURCHASE' AND source_kind IS NOT NULL AND source_kind='PURCHASE_INVOICE' AND source_no IS NOT NULL AND char_length(btrim(source_no))>0 AND source_snapshot IS NOT NULL AND source_digest IS NOT NULL AND source_status IS NOT NULL)")
rule(D, 'source_snapshot', "source_snapshot IS NULL OR jsonb_typeof(source_snapshot)='object'")
rule(D, 'source_digest', "source_digest IS NULL OR source_digest ~ '^[0-9a-f]{64}$'")
rule(D, 'source_status', "source_status IS NULL OR source_status IN ('draft','confirmed','cancelled')")
rule(D, 'amount,currency', "(amount IS NULL AND currency IS NULL) OR (amount IS NOT NULL AND amount >= 0 AND currency IS NOT NULL AND currency ~ '^[A-Z]{3}$')")
CONSTRAINTS.append(c(D, 'UK_PARTIAL', S+['source_kind','source_no'],
    "UNIQUE (workspace_id,generation_id,source_kind,source_no) WHERE status='IN_REVIEW' AND kind='ERP_PURCHASE'", '동일 원천의 진행 결재 1건'))
rule(DS, 'status,decided_at,decision_reason',
     "(status IN ('WAITING','SKIPPED') AND decided_at IS NULL AND decision_reason IS NULL) OR "
     "(status='APPROVED' AND decided_at IS NOT NULL) OR "
     "(status='REJECTED' AND decided_at IS NOT NULL AND decision_reason IS NOT NULL AND char_length(btrim(decision_reason))>=2)")

DOC_EVENTS = ['CREATED','DRAFT_SAVED','SOURCE_REFRESHED','ROUTE_SELECTED','SUBMITTED','APPROVED','REJECTED','WITHDRAWN','RESUBMISSION_CREATED']
POST_EVENTS = ['CREATED','DRAFT_SAVED','PUBLISHED','WITHDRAWN','CORRECTION_CREATED']
for t, owner, types in [(DE, 'document', DOC_EVENTS), (BE, 'post', POST_EVENTS)]:
    key(t, owner+'_id', 'event_seq')
    rule(t, 'event_seq,'+owner+'_version', f'event_seq > 0 AND {owner}_version > 0')
    rule(t, 'actor_kind', "actor_kind IN ('GUEST','MEMBER','SEED')")
    rule(t, 'event_type', 'event_type IN ('+','.join(repr(v) for v in types)+')')
    rule(t, 'event_type,reason', "event_type NOT IN ('REJECTED','WITHDRAWN') OR (reason IS NOT NULL AND char_length(btrim(reason))>=2)")
    CONSTRAINTS.append(c(t, 'SERVICE/DB_POLICY', [owner+'_id'], '사건는 추가 전용. 실제 AuthContext 주체만 기록. SEED 주체는 복사 유지, 토큰/별칭 저장 금지. 세대 정리 외 수정·삭제 없음', 'D64·D68 감사'))
rule(DE, 'step_seq,event_type', "(event_type IN ('APPROVED','REJECTED') AND step_seq IS NOT NULL AND step_seq BETWEEN 1 AND 3) OR (event_type NOT IN ('APPROVED','REJECTED') AND step_seq IS NULL)")
key(B, 'post_no')
key(B, 'previous_post_id')
rule(B, 'previous_post_id,id', 'previous_post_id IS NULL OR previous_post_id <> id')
rule(B, 'board_kind', "board_kind IN ('NOTICE','FREE')")
rule(B, 'status,published_at,withdrawn_at,withdraw_reason',
     "(status='DRAFT' AND published_at IS NULL AND withdrawn_at IS NULL AND withdraw_reason IS NULL) OR "
     "(status='PUBLISHED' AND published_at IS NOT NULL AND withdrawn_at IS NULL AND withdraw_reason IS NULL) OR "
     "(status='WITHDRAWN' AND published_at IS NOT NULL AND withdrawn_at IS NOT NULL AND withdraw_reason IS NOT NULL AND char_length(btrim(withdraw_reason))>=2)")
for t, fields, policy in [
    (P, ['is_active'], '진행 문서·초안 참조와 마지막 BOARD_ADMIN 비활성화 거부. 삭제 없음'),
    (RT, ['version'], '공간 잠금·expectedVersion, 1~3명 연속 순서, 템플릿 변경은 문서에 영향 없음'),
    (D, ['status'], 'TX-G1~4: 상신 후 원문·결재선 불변, 순차 승인/반려, 최초 승인 전 회수만. 재상신은 종결 원문 연결·새 행'),
    (D, ['source_digest'], 'ERP interface 스냅샷 재검사. 날짜/시각 digest 제외. 게스트 복사 의미 digest 보존'),
    (DS, ['status'], '자기/중복 결재 금지. 단계 수·순서·문서 상태 일치. 상신 후 담당자 스냅샷 불변'),
    (B, ['status'], '게시 후 원문 불변. 정정은 새 글·철회 사유 이력. 작성 역할·공지 BOARD_ADMIN 검사'),
]:
    CONSTRAINTS.append(c(t, 'SERVICE/DB_POLICY', fields, policy, 'FS-030 서비스 구현 대상(b)'))

RELATIONS = [dict(source=t['name'],columns=S,target='core.data_generation',target_columns=['workspace_id','id'],on_delete='RESTRICT',on_update='RESTRICT',note='공간·세대 앵커') for t in TABLES]
for source, field, target in [(RS,'route_id',RT),(RS,'person_id',P),(D,'drafter_id',P),(D,'route_id',RT),(D,'previous_document_id',D),(DS,'document_id',D),(DS,'person_id',P),(DE,'document_id',D),(DE,'acting_person_id',P),(B,'author_id',P),(B,'previous_post_id',B),(BE,'post_id',B),(BE,'acting_person_id',P)]:
    RELATIONS.append(r(source,[field],target,'GW 내부 복합 참조'))
    CONSTRAINTS.append(c(source,'INDEX',S+[field],reason='FK 조회/참조 삭제 검사'))
for t, fields in [(D,['status','submission_order']),(D,['drafter_id','status','serial']),(D,['source_kind','source_no','submission_order']),(DS,['person_id','status','document_id']),(B,['board_kind','status','serial'])]:
    CONSTRAINTS.append(c(t,'INDEX',S+fields,reason='목록·배지 조회'))

STATES = [dict(table=t,column='status',values=values,default=values[0],transition=transition) for t,values,transition in [
    (D,['DRAFT','IN_REVIEW','APPROVED','REJECTED','WITHDRAWN'],'초안→진행→승인/반려/회수. 종결 후 불변'),
    (DS,['WAITING','APPROVED','REJECTED','SKIPPED'],'대기→승인/반려/건너뜀. 이후 불변'),
    (B,['DRAFT','PUBLISHED','WITHDRAWN'],'초안→게시→철회. 본문은 게시 후 불변')]]


def apply(d):
    names = {t['name'] for t in d['tables'] if t['name'].startswith('gw.')}
    if names:
        # 후속 GW-a가 표를 추가해도 최초 8표가 모두 있으면 재적용하지 않는다.
        if not {t['name'] for t in TABLES}.issubset(names):
            raise ValueError('partial GW schema: refusing to hide incomplete application')
        return False
    d['tables'].extend(copy.deepcopy(TABLES))
    d['constraints'].extend(copy.deepcopy(CONSTRAINTS))
    d['relations'].extend(copy.deepcopy(RELATIONS))
    d['states'].extend(copy.deepcopy(STATES))
    for constraint in d['constraints']:
        if constraint['table'] in {'core.workspace_module','core.app_review'} and constraint['kind']=='CHECK' and 'module_key IN' in constraint['expression'] and "'gw'" not in constraint['expression']:
            constraint['expression'] = constraint['expression'].rstrip().removesuffix(')') + ", 'gw')"
    for code in d['code_lists']:
        if code['target'] in {'core.workspace_module','core.app_review'} and code['column']=='module_key':
            if 'gw' not in code['values']:
                code['values'].append('gw')
    # 2026-10-01 main 병합: 임시 0.15.0-gw → 0.16.0(FS-040이 0.15.0)
    d.update(version='0.16.0',task='FS-030a',date='2026-10-01',migration_revision='fs030b_gw_module')
    d['change_log'].append(dict(version='0.16.0',task='FS-030a',date='2026-10-01',change='GW 8테이블·모듈 키 및 기존 공간 행. FS-040 뒤 신규 revision, 교차 업무 FK0',status='FS-030a DB 검증 대상'))
    return True


if __name__ == '__main__':
    data = json.loads(SCHEMA.read_text())
    changed = apply(data)
    if changed:
        SCHEMA.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'changed':changed,'tables':len(data['tables']),'constraints':len(data['constraints']),'relations':len(data['relations'])}))

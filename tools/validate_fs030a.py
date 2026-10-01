"""Independent GW invariants; not an API/state-machine implementation."""
from audit_schema_isolation import audit

NAMES = {'gw.'+n for n in ('person','approval_route','route_step','approval_document','approval_step','approval_event','board_post','board_event')}
S = ['workspace_id','generation_id']


def validate_gw(d):
    errors = []
    def require(ok, message):
        if not ok:
            errors.append('FS-030: '+message)
    tables = {t['name']:t for t in d['tables']}
    require({n for n in tables if n.startswith('gw.')} == NAMES, 'eight GW tables')
    cs = d['constraints']
    def unique(t, cols):
        return any(c['table']==t and c['kind']=='UK' and c['columns']==S+cols for c in cs)
    for t in NAMES:
        require(unique(t,['id']), t+' scope key')
        cols = {c['name']:c for c in tables.get(t,{}).get('columns',[])}
        require(cols.get('created_at',{}).get('default')=='clock_timestamp()',t+' database clock')
        require(not any(n in cols for n in ('user_id','erp_id','invoice_id')),t+' no account/source FK identifiers')
    for t, cols in [('gw.approval_step',['document_id','seq']),('gw.approval_step',['document_id','person_id']),('gw.route_step',['route_id','seq']),('gw.route_step',['route_id','person_id']),('gw.approval_document',['previous_document_id']),('gw.approval_document',['submission_order']),('gw.approval_event',['document_id','event_seq']),('gw.board_post',['previous_post_id']),('gw.board_event',['post_id','event_seq'])]:
        require(unique(t,cols), t+' unique '+','.join(cols))
    require(any(c['table']=='gw.approval_document' and c['kind']=='UK_PARTIAL' and c['columns']==S+['source_kind','source_no'] and "status='IN_REVIEW'" in c['expression'] for c in cs),'one active source approval')
    for t in ('core.workspace_module','core.app_review'):
        require(any(c['table']==t and c['kind']=='CHECK' and "'gw'" in c['expression'] for c in cs),t+' GW module key')
    for t, field in [('gw.route_step','seq'),('gw.approval_step','seq')]:
        require(any(c['table']==t and c['kind']=='CHECK' and c['expression']=='seq BETWEEN 1 AND 3' for c in cs),t+' step bounds')
    for t, field in [('gw.approval_document','source_snapshot'),('gw.approval_document','status'),('gw.approval_step','status'),('gw.board_post','status')]:
        require(any(c['table']==t and c['kind']=='CHECK' and field in c['columns'] for c in cs),t+' check '+field)
    errors.extend(audit(d))
    return errors

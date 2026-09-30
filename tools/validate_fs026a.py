"""Static contracts for FS-026, not proof of service policy implementation."""
def validate_extension(data):
    errors = []
    tables = {t['name']: t for t in data['tables']}
    expected = {'inbound_notice', 'inbound_notice_line', 'source_claim', 'stock_reservation', 'stock_reservation_line'}
    for name in expected:
        if 'wms.'+name not in tables: errors.append('FS-026: missing '+name)
    cs = data['constraints']
    for name in ('source_key', 'notice_id'):
        if not any(c['table']=='wms.source_claim' and c['kind']=='UK_PARTIAL' and c['columns']==['workspace_id','generation_id',name] and c['expression'].endswith("WHERE status <> 'RELEASED'") for c in cs):
            errors.append('FS-026: missing active claim uniqueness '+name)
    for t in ('inbound_notice_line','stock_reservation_line'):
        for predicate in ('lot_no IS NULL', 'lot_no IS NOT NULL'):
            if not any(c['table']=='wms.'+t and c['kind']=='UK_PARTIAL' and c['expression'].endswith('WHERE '+predicate) for c in cs):
                errors.append('FS-026: missing NULL-safe LOT uniqueness '+t)
    for reason in ('검수 수량 전체 입력 및 합계','소진 전표와 원천 동시 기록','기본 위치 정상만'):
        if not any(c['kind']=='CHECK' and c['reason']==reason for c in cs): errors.append('FS-026: missing CHECK '+reason)
    for reason in ('원천 단일 경로','예약 가능 수량','예약 소진 원자성'):
        if not any(c['kind']=='SERVICE/DB_POLICY' and c['reason']==reason for c in cs): errors.append('FS-026: missing SERVICE policy '+reason)
    return errors

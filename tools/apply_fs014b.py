"""FS-014b: v0.7.0 -> v0.8.0 accounting metadata, 61 -> 72 tables.

No DDL, database access or seed generation. Validate, SHA256 backup, atomic
replace. --check is read-only; valid applied input is a byte/mtime-level no-op.
"""
import argparse
import copy
import hashlib
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from validate_db_design import validate, design_names

ROOT = Path(__file__).resolve().parents[1]
S = ['workspace_id', 'generation_id']
BEFORE = {'core': 11, 'mes': 21, 'erp': 16, 'fems': 13}
AFTER = dict(BEFORE, erp=27)
NEW = {'erp.'+n for n in ['receivable','receipt','receipt_apply','payable','payment','payment_apply',
                         'purchase_invoice','purchase_invoice_line','tax_invoice','account','posting_rule']}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def counts(d):
    return dict(Counter(t['name'].split('.')[0] for t in d['tables']))


def check(d, task):
    errors = validate(d, design_names(task))
    need(not errors, '\n'.join(errors))


def col(name, label, type_, nullable=False, default=None, rule=''):
    return dict(name=name, label=label, type=type_, nullable=nullable, default=default, rule=rule)


def transform(original):
    need(original.get('version') == '0.7.0' and original.get('task') == 'FS-014', 'Expected v0.7.0 / FS-014')
    need(original.get('migration_revision') is None, 'DB-applied metadata is out of scope')
    need(counts(original) == BEFORE, f'Unexpected input counts: {counts(original)}')
    check(original, 'FS-014')
    d = copy.deepcopy(original)
    tables = {t['name']: t for t in d['tables']}
    need(not NEW & set(tables), 'Partial accounting application detected')
    base = {c['name']: c for c in tables['erp.sales_record']['columns']}
    money = 'numeric(18,2)'

    def constraint(table, kind, columns, expression, reason):
        d['constraints'].append(dict(table=table, kind=kind, columns=columns, expression=expression, reason=reason))
    def uk(t, columns, reason):
        constraint(t, 'UK', columns, '', reason)
    def ck(t, columns, expression, reason):
        constraint(t, 'CHECK', columns, expression, reason)
    def policy(t, columns, expression, reason):
        constraint(t, 'SERVICE/DB_POLICY', columns, expression, reason)
    def fk(source, columns, target, target_columns=None, note='같은 공간·세대 ERP 내부 참조'):
        d['relations'].append(dict(source=source, columns=S+columns, target=target,
                                   target_columns=S+(target_columns or ['id']), on_delete='RESTRICT', on_update='RESTRICT', note=note))
    def currency():
        return col('currency','통화','varchar(3)',default="'KRW'",rule='1차 KRW 단일; 외화 제외')
    def add(name, label, sub, body, note):
        t = dict(name=name,label=label,scope='generation',phase='M3',sub_module=sub,retention='세대 정리',
                 guest_cleanup='소명·세금계산서 등 자식 우선 삭제',note=note,
                 columns=[copy.deepcopy(base[k]) for k in ['id',*S]]+body+[copy.deepcopy(base['created_at'])])
        tables[name]=t;d['tables'].append(t)
        constraint(name,'PK',['id'],'','기본키');uk(name,S+['id'],'공간·세대 복합 참조 대상')
        d['relations'].append(dict(source=name,columns=S,target='core.data_generation',target_columns=['workspace_id','id'],
                                   on_delete='RESTRICT',on_update='RESTRICT',note='공간·세대 범위 앵커'))
        if any(c['name']=='currency' for c in body):
            ck(name,['currency'],"currency = 'KRW'",'1차 KRW 단일')
    def state(t, values, transition):
        d['states'].append(dict(table=t,column='status',values=values,default=values[0],transition=transition))

    # Existing sales record is born recognized in TX-09, not a draft document.
    sales='erp.sales_record'
    tables[sales]['columns'] += [currency(),col('cancelled_at','매출 취소 시각','timestamptz',True),
                                col('cancel_reason','매출 취소 사유','varchar(300)',True)]
    tables[sales]['note']='FS-014b: TX-09 생성 즉시 매출 인식·확정. 금액 불변, 취소는 표시만 남기고 원금 보존'
    uk(sales,S+['id','partner_id','currency'],'채권·세금계산서의 거래처·통화 일치 참조')
    ck(sales,['currency'],"currency = 'KRW'",'1차 KRW 단일')
    ck(sales,['supply_amount','tax_amount','total_amount'],'supply_amount >= 0 AND tax_amount >= 0 AND total_amount >= 0','음수 전표 제외')
    ck(sales,['cancelled_at','cancel_reason'],"(cancelled_at IS NULL AND cancel_reason IS NULL) OR (cancelled_at IS NOT NULL AND length(btrim(cancel_reason)) > 0 AND cancel_reason IS NOT NULL)",'취소 시각·사유 동시 기록')
    policy(sales,['recognized_at','total_amount'],
           'TX-09 생성이 확정이다. 출하·매출·receivable 1건을 같은 트랜잭션에서 생성한다. amount=total_amount, 거래처·통화 일치. 실패 시 전체 롤백. 수기 채권 생성 금지', '채권 파생 생성')
    policy(sales,['cancelled_at','cancel_reason','total_amount'],
           '확정 금액·거래처·통화·근거 출하 수정 및 일반 삭제 금지. 취소는 이 매출에서만 단방향 처리한다. receipt_apply가 0행이어야 한다. tax_invoice가 issued이면 거부, pending이면 같은 트랜잭션에서 물리 삭제, 없으면 소명 조건만 확인한다. 채권 원금은 유지하고 취소 매출의 채권은 유효 잔액·상태·미리보기에서 제외한다. 출하 물류를 되돌리지 않으며 재확정·음수 역분개는 지원하지 않는다', '매출 취소 계약')

    # Simplified purchase: header + line only, no ordering/receiving/WMS.
    purchase='erp.purchase_invoice'
    add(purchase,'매입 전표(간이)','purchase',[
        col('invoice_no','매입 전표번호','varchar(40)'),col('partner_id','공급 거래처','bigint'),
        col('invoice_date','매입일','date'),col('due_date','지급 기한','date',True),currency(),
        col('supply_amount','공급가액',money,default='0'),col('tax_amount','세액',money,default='0'),col('total_amount','합계',money,default='0'),
        col('status','상태','varchar(20)',default="'draft'",rule='draft / confirmed / cancelled'),
        col('confirmed_at','확정 시각','timestamptz',True),col('cancelled_at','취소 시각','timestamptz',True),
        col('cancel_reason','취소 사유','varchar(300)',True)],'원재료 매입의 최소 입력. 확정과 동시에 payable 생성')
    uk(purchase,S+['invoice_no'],'세대 내 전표번호 유일');uk(purchase,S+['id','partner_id','currency'],'채무의 거래처·통화 일치 참조')
    uk(purchase,S+['id','currency'],'매입 명세 통화 일치 참조');fk(purchase,['partner_id'],'erp.partner')
    ck(purchase,['supply_amount','tax_amount','total_amount'],'supply_amount >= 0 AND tax_amount >= 0 AND total_amount = supply_amount + tax_amount','음수 제외·합계 정합성')
    ck(purchase,['status','confirmed_at','cancelled_at','cancel_reason'],
       "(status = 'draft' AND confirmed_at IS NULL AND cancelled_at IS NULL AND cancel_reason IS NULL) OR (status = 'confirmed' AND confirmed_at IS NOT NULL AND cancelled_at IS NULL AND cancel_reason IS NULL) OR (status = 'cancelled' AND cancelled_at IS NOT NULL AND cancel_reason IS NOT NULL AND length(btrim(cancel_reason)) > 0)",'매입 상태·확정·취소 메타데이터 일치')
    state(purchase,['draft','confirmed','cancelled'],'draft→confirmed→cancelled 또는 draft→cancelled; 취소 후 재확정 금지')
    policy(purchase,['status','total_amount'],
           'draft에서만 헤더·명세 수정/삭제. 확정 시 SUPPLIER 거래처, 명세 1개 이상, 공급가액·세액·합계와 명세 합계를 잠금 안에서 대조한다. payable 1건을 같은 트랜잭션에서 생성한다. 확정 후 헤더 금액·거래처·통화·명세 불변. 취소는 이 매입 전표에서만 수행하고 payment_apply가 0행이어야 한다. 채무 원금 보존, 취소 채무는 유효 잔액·상태·미리보기에서 제외한다. tax_invoice는 매출 전용이므로 매입 취소와 무관하다', '채무 파생 생성 및 매입 취소')
    line='erp.purchase_invoice_line'
    add(line,'매입 명세','purchase',[
        col('purchase_invoice_id','매입 전표','bigint'),col('line_no','행 번호','integer'),col('item_id','매입 품목','bigint'),
        col('quantity','매입 수량','numeric(18,3)'),col('unit','수량 단위','varchar(10)'),col('unit_price','단가','numeric(18,4)'),currency(),
        col('supply_amount','공급가액',money),col('tax_amount','세액',money),col('total_amount','합계',money)],'구매발주·입고검수 없음. 원재료 계정에 해당하는 매입만 대상')
    uk(line,S+['purchase_invoice_id','line_no'],'전표 내 행 번호 유일')
    fk(line,['purchase_invoice_id','currency'],purchase,['id','currency']);fk(line,['item_id'],'erp.item')
    ck(line,['line_no','quantity','unit_price','supply_amount','tax_amount','total_amount'],
       'line_no >= 1 AND quantity > 0 AND unit_price >= 0 AND supply_amount >= 0 AND tax_amount >= 0 AND total_amount = supply_amount + tax_amount','수량·금액 범위 및 합계')
    policy(line,['purchase_invoice_id','item_id','unit','supply_amount','tax_amount'],
           '부모 draft에서만 등록·수정·삭제. 품목과 단위를 검증하고 원재료 매입만 허용한다. 공급가액·세액은 단일 금액·반올림 정책으로 계산/대조한다. 임의 세율 또는 법정 적합성을 CHECK로 가정하지 않는다. 확정 명세는 불변', '매입 명세 불변 및 금액 정책')

    # Receivables/payables have neither persisted balance nor persisted status.
    for ledger,label,parent,parent_id in [('receivable','매출채권',sales,'sales_record_id'),('payable','매입채무',purchase,'purchase_invoice_id')]:
        name='erp.'+ledger
        add(name,label,'accounting',[
            col(parent_id,'원천 확정 거래','bigint'),col('partner_id','거래처','bigint'),
            col('amount','원금',money,rule='원천 total_amount와 일치; 확정 후 불변'),currency(),
            col('due_date','결제 기한','date',True)],'원천 확정 거래의 파생물. 잔액·상태 저장 없음; 원천 취소 여부로 유효 집계 제외')
        uk(name,S+[parent_id],'원천 거래당 채권·채무 1건');uk(name,S+['id','partner_id','currency'],'소명 거래처·통화 일치 참조')
        fk(name,[parent_id,'partner_id','currency'],parent,['id','partner_id','currency'])
        ck(name,['amount'],'amount >= 0','원금 음수 금지')
        policy(name,[parent_id,'amount','due_date'],
               '수기 등록·일반 수정·삭제 금지. 원천 확정과 같은 트랜잭션에서 원금=total_amount로 1건 생성. 원금·근거·거래처·통화·기한은 확정 후 불변. 취소는 상위 거래를 통해서만 수행한다', '원금 파생 및 불변')
        policy(name,['amount'],
               '유효 원천 거래의 잔액 = amount - SUM(소명.amount), 소명 없으면 합계 0. 잔액 0이면 CLOSED, 0<잔액<원금이면 PARTIAL, 잔액=양의 원금이면 OPEN. 원금 0은 CLOSED 우선. 잔액·상태·합계 캐시를 저장하지 않는다', '잔액·상태 조회 파생')
    for cash,label,no,datecol,datelabel,ledger in [('receipt','수금','receipt_no','received_on','수금일','receivable'),('payment','지급','payment_no','paid_on','지급일','payable')]:
        name='erp.'+cash
        add(name,label,'accounting',[
            col(no,label+' 번호','varchar(40)'),col('partner_id','거래처','bigint'),col(datecol,datelabel,'date'),
            col('amount',label+'액',money),currency(),col('status','상태','varchar(20)',default="'draft'",rule='draft / confirmed'),
            col('confirmed_at','금액 확정 시각','timestamptz',True)],'확정 후 금액 고정. 소명 추가·물리 삭제는 계속 허용; 미소명 잔여 저장 없음')
        uk(name,S+[no],'세대 내 번호 유일');uk(name,S+['id','partner_id','currency'],'소명 거래처·통화 일치 참조');fk(name,['partner_id'],'erp.partner')
        ck(name,['amount'],'amount > 0','수금·지급액 양수')
        ck(name,['status','confirmed_at'],"(status = 'draft' AND confirmed_at IS NULL) OR (status = 'confirmed' AND confirmed_at IS NOT NULL)",'상태·확정시각 일치')
        state(name,['draft','confirmed'],'draft→confirmed; 금액 불변, 이후 소명 추가·물리 삭제 허용')
        policy(name,['status','amount','partner_id','currency'],
               'draft에서만 수정·삭제. 확정 후 amount·거래처·통화·일자 수정 및 일반 삭제/상태 되돌림 금지. confirmed 이후에도 소명 추가·취소를 허용한다. 과입금/미소명 잔여는 거부하지 않고 amount-SUM(소명.amount)으로 조회한다. 선수금·외화·음수 전표 없음', '수금·지급 금액 확정과 소명 분리')
        apply='erp.'+cash+'_apply'
        add(apply,label+' 소명','accounting',[
            col(cash+'_id',label,'bigint'),col(ledger+'_id','대상 '+('채권' if cash=='receipt' else '채무'),'bigint'),
            col('partner_id','거래처 대사','bigint'),currency(),col('amount','소명액',money),
            col('apply_key','소명 요청 키','varchar(100)',rule='core.request_receipt 멱등 결과와 함께 사용'),
            col('applied_at','소명 시각','timestamptz')],'1행=한 건의 소명. 취소는 물리 DELETE; 이력은 core.audit_event. 1행=분개 미리보기 1세트')
        uk(apply,S+['apply_key'],'동일 소명 요청 중복 차단')
        fk(apply,[ledger+'_id','partner_id','currency'],'erp.'+ledger,['id','partner_id','currency'])
        fk(apply,[cash+'_id','partner_id','currency'],name,['id','partner_id','currency'])
        ck(apply,['amount'],'amount > 0','소명액 양수')
        ck(apply,['apply_key'],"length(btrim(apply_key)) > 0",'빈 요청 키 금지')
        for ref in [ledger+'_id',cash+'_id']:
            constraint(apply,'INDEX',S+[ref],'','소명 합계 조회와 참조 탐색')
        policy(apply,[ledger+'_id',cash+'_id','amount'],
               '공간→세대 및 필요한 앞 단계 원천 거래 잠금 후 7단계 채권·채무→수금·지급→소명 순서. receivable.id 오름차순 다음 receipt.id 오름차순, 지급은 payable.id 다음 payment.id 오름차순. 혼합 요청은 receivable→payable→receipt→payment→receipt_apply→payment_apply, 각 테이블 id 오름차순. 자식 잠금 후 부모 잠금 금지', '회계 잠금 순서')
        policy(apply,[ledger+'_id',cash+'_id','amount'],
               '추가·삭제를 같은 트랜잭션에서 수행. 부모 잠금 후 최신 소명 합계를 새로 조회하여 SUM(소명.amount)<=수금/지급.amount 및 SUM(소명.amount)<=채권/채무.amount 두 한도를 모두 검사한다. 범위·거래처·KRW 일치, 수금/지급 confirmed, 원천 거래 미취소를 재확인하고 위반 시 전체 롤백. 직접 DB 쓰기는 이 정책으로 보호되지 않는다', '소명 양쪽 합계 한도')
        policy(apply,['apply_key','amount'],
               '소명 행 UPDATE 금지. 변경은 기존 소명 물리 DELETE 후 별도 키로 신규 등록. 삭제 이력은 core.audit_event summary에 S·양쪽 부모 ID·소명 ID·apply_key·금액·통화·사유를 저장하고 같은 트랜잭션에 포함한다. core에서 ERP로 FK를 만들지 않는다. 취소는 멱등 처리하며 삭제 실패나 감사 기록 실패 시 전체 롤백', '소명 물리 삭제 및 감사')
        policy(apply,['apply_key'],
               '등록/취소 요청은 core.request_receipt로 멱등 처리. 성공 후 재요청은 재등록하지 않는다. 소명 물리 삭제 이후에도 예전 등록 키를 재사용해 복원하지 않는다. 요청 결과 보존 기간과 재시도 허용 기간을 일치시키며 만료 키 재사용은 거부한다. 새 의도는 새 키로만 등록한다', '소명 재요청 중복 차단')
        policy(apply,['amount'],
               '이 소명 1행의 amount로 분개 1세트를 조회 계산한다. 수금/지급 원액을 분개하지 않는다. 소명 삭제 시 해당 미리보기도 사라진다. 미소명 잔여 안내는 분개 표 밖에 표시한다. FIFO는 화면 기본 제안일 뿐 저장하지 않는다', '소명 행별 비저장 미리보기')

    tax='erp.tax_invoice'
    add(tax,'매출 세금계산서 발급확인','accounting',[
        col('sales_record_id','인식된 매출','bigint'),col('partner_id','매출 거래처','bigint'),currency(),
        col('status','발급 상태','varchar(20)',default="'pending'",rule='pending 발급대기 / issued 발급완료'),
        col('approval_no','수기 승인번호','varchar(60)',True),col('issued_on','수기 발급일','date',True)],
        '매출 전용, sales_record당 최대 1건. 명세·월합계·국세청 연동 없음; 금액은 매출에서 조회')
    uk(tax,S+['sales_record_id'],'매출당 세금계산서 1건');fk(tax,['sales_record_id','partner_id','currency'],sales,['id','partner_id','currency'])
    constraint(tax,'UK_PARTIAL',S+['approval_no'], 'UNIQUE (workspace_id, generation_id, approval_no) WHERE approval_no IS NOT NULL','세대 내 입력 승인번호 중복 차단')
    ck(tax,['status','approval_no','issued_on'],"(status = 'pending' AND approval_no IS NULL AND issued_on IS NULL) OR (status = 'issued' AND approval_no IS NOT NULL AND length(btrim(approval_no)) > 0 AND issued_on IS NOT NULL)",'두 발급 상태와 수기 필드 일치')
    state(tax,['pending','issued'],'pending→issued; issued 불변. pending은 매출 취소 시 함께 물리 삭제')
    policy(tax,['sales_record_id','status','issued_on'],
           '이미 인식된 미취소 매출에만 생성·발급확인 가능. 매출 잠금 후 재확인하며 선발행 금지. issued_on은 recognized_at의 Asia/Seoul 기준 날짜 이상. pending은 매출 취소와 같은 트랜잭션에서 삭제, issued는 수정·삭제 및 매출 취소 금지. 매입과 연결하지 않는다. 수기 승인번호는 국세청 승인 검증 결과가 아니다', '세금계산서 선후 및 취소 계약')

    account='erp.account'
    account_names={'AR':'외상매출금','PRODUCT_SALES':'제품매출','VAT_PAYABLE':'부가세예수금','BANK':'보통예금',
                   'RAW_MATERIAL':'원재료','VAT_RECEIVABLE':'부가세대급금','AP':'외상매입금'}
    add(account,'계정과목','accounting_preview',[
        col('account_code','계정 코드','varchar(40)'),col('account_name','계정명','varchar(100)')],
        '읽기 전용 미리보기용 7개 계정만. 전체 계정과목표·회계 전표 없음')
    uk(account,S+['account_code'],'세대 내 계정 코드 유일');uk(account,S+['id','account_code'],'분개 규칙의 계정 코드 일치 참조')
    ck(account,['account_code','account_name'],' OR '.join(f"(account_code = '{code}' AND account_name = '{label}')" for code,label in account_names.items()),'허용 계정 7개 및 명칭 고정')
    policy(account,['account_code','account_name'],'7개 계정 정의만 초기 데이터로 공급할 예정. 일반 사용자 쓰기 금지, 세대 초기화·정리만 허용. 이 작업은 seed를 생성하지 않는다', 'B층 계정 읽기 전용')
    d['code_lists'].append(dict(target=account,column='account_code',values=list(account_names),default=None,note='; '.join(k+'='+v for k,v in account_names.items())))
    rule='erp.posting_rule'
    templates=[('SALE',1,'DEBIT','AR','TOTAL'),('SALE',2,'CREDIT','PRODUCT_SALES','SUPPLY'),('SALE',3,'CREDIT','VAT_PAYABLE','TAX'),
               ('RECEIPT',1,'DEBIT','BANK','APPLY'),('RECEIPT',2,'CREDIT','AR','APPLY'),
               ('PURCHASE',1,'DEBIT','RAW_MATERIAL','SUPPLY'),('PURCHASE',2,'DEBIT','VAT_RECEIVABLE','TAX'),('PURCHASE',3,'CREDIT','AP','TOTAL'),
               ('PAYMENT',1,'DEBIT','AP','APPLY'),('PAYMENT',2,'CREDIT','BANK','APPLY')]
    add(rule,'분개 미리보기 규칙','accounting_preview',[
        col('transaction_kind','거래 유형','varchar(20)',rule='SALE / RECEIPT / PURCHASE / PAYMENT'),col('line_no','분개 표시 순서','integer'),
        col('entry_side','차대 구분','varchar(6)',rule='DEBIT / CREDIT'),col('account_id','계정과목','bigint'),
        col('account_code','계정 코드 대사','varchar(40)'),col('amount_basis','참조 금액 종류','varchar(10)',rule='TOTAL / SUPPLY / TAX / APPLY')],
        '규칙 1행은 미리보기 1줄. 4거래 유형·10행 고정 조합. 조건식·분기 엔진·분개 결과 저장 없음')
    uk(rule,S+['transaction_kind','line_no'],'거래 유형별 표시 순서 유일');fk(rule,['account_id','account_code'],account,['id','account_code'])
    fields=['transaction_kind','line_no','entry_side','account_code','amount_basis']
    ck(rule,fields,' OR '.join('('+' AND '.join(f"{k} = {v}" if isinstance(v,int) else f"{k} = '{v}'" for k,v in zip(fields,row))+')' for row in templates),'허용 분개 규칙 10개 조합')
    policy(rule,fields,
           '일반 사용자 쓰기 금지. 정의된 4종·10행 규칙이 완비된 경우에만 미리보기. 누락·불일치 시 계산 불가로 표시. SALE은 미취소 sales_record 1행, PURCHASE는 confirmed 매입 전표 1행, RECEIPT/PAYMENT는 각각 receipt_apply/payment_apply 1행을 1세트로 삼는다. SUPPLY/TAX/TOTAL은 원천 금액, APPLY는 소명액. 차대 합계를 대조하고 결과를 저장하지 않는다. 미소명 잔여는 분개 표 밖 안내', 'B층 고정 규칙·비저장 미리보기')
    d['code_lists'].append(dict(target=rule,column='transaction_kind',values=['SALE','RECEIPT','PURCHASE','PAYMENT'],default=None,note='매출 인식 / 수금 소명 / 매입 / 지급 소명'))
    # Codes/numbers entered by users must not be blank.
    for table,column in [(purchase,'invoice_no'),('erp.receipt','receipt_no'),('erp.payment','payment_no'),(line,'unit')]:
        ck(table,[column],f'length(btrim({column})) > 0','빈 번호·단위 금지')
    d.update(version='0.8.0',task='FS-014b',date='2026-09-22',basis='FS-013 D7 + FS-014b 사용자 확정 규칙·추가 결정',migration_revision=None)
    d['sources'].append('FS-014b ERP 회계 A·B층 설계 근거')
    d['change_log'].append(dict(version='0.8.0',task='FS-014b',date='2026-09-22',
                               change='ERP 회계 11개 신설. 소명 잔액·상태 조회 파생, 소명 물리 삭제, 매출 전용 세금계산서, 비저장 분개 규칙. 72테이블',status='정적 메타데이터 검증 대상 / DB·서비스 미적용'))
    need(counts(d)==AFTER,'Output count mismatch')
    check(d,'FS-014b')
    return d


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schema',type=Path,default=ROOT/'docs/db/schema-metadata/schema.json')
    parser.add_argument('--backup-dir',type=Path)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    try:
        raw=args.schema.read_bytes();d=json.loads(raw)
        need(d.get('migration_revision') is None,'DB-applied metadata is out of scope')
        if d.get('version')=='0.8.0' and d.get('task')=='FS-014b':
            need(counts(d)==AFTER,'Invalid applied counts');check(d,'FS-014b')
            print('FS-014b already applied and valid; no files changed.');return 0
        result=transform(d)
        payload=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
        if args.check:
            print(json.dumps(dict(check='passed',tables=counts(result),total=len(result['tables']),written=False)));return 0
        need(args.schema.read_bytes()==raw,'Source changed during validation')
        backup_dir=args.backup_dir or args.schema.parent/'backups';backup_dir.mkdir(parents=True,exist_ok=True)
        backup=backup_dir/f'schema.before-FS-014b.{hashlib.sha256(raw).hexdigest()}.json'
        if backup.exists():need(backup.read_bytes()==raw,'Existing backup content mismatch')
        else:
            with backup.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(dir=args.schema.parent,prefix='.fs014b-',delete=False) as f:
                temporary=Path(f.name);f.write(payload);f.flush();os.fsync(f.fileno())
            temporary.chmod(args.schema.stat().st_mode & 0o777)
            need(args.schema.read_bytes()==raw,'Source changed before replacement')
            os.replace(temporary,args.schema)
        finally:
            if temporary and temporary.exists():temporary.unlink()
        print(json.dumps(dict(applied='FS-014b',tables=counts(result),total=len(result['tables']),backup=str(backup)),ensure_ascii=False,indent=2))
        return 0
    except (OSError,ValueError,KeyError,TypeError,StopIteration) as exc:
        print(f'ABORT: {exc}');return 1


if __name__=='__main__':
    raise SystemExit(main())

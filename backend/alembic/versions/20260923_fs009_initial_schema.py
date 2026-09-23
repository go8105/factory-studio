"""FS-009 initial schema, hand-authored from v0.9.1.

C numbers are zero-based schema.json constraints indexes; R numbers are relations indexes.
SERVICE/DB_POLICY is deliberately not implemented as a database constraint.
Source SHA256: 7e97937e7bd0df6fdae97b309444dbfdac584dd2efae71ad4f0bad7eed2d5e44
"""

from alembic import op

revision = "7e97937e7bd0"
down_revision = None
branch_labels = None
depends_on = None

# 고정된 최초 리비전의 반복 SQL 표기만 줄인다. 설계 JSON을 읽지 않는다.
ID = "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL"
S = "workspace_id bigint NOT NULL, generation_id bigint NOT NULL"
CREATED = "created_at timestamptz NOT NULL DEFAULT now()"
TABLES: list[str] = []


def table(name: str, columns: str, *, scoped: bool = True, after: str = "") -> None:
    prefix = f"{ID}, {S}" if scoped else ID
    suffix = f", {after}" if after else ""
    op.execute(f"CREATE TABLE {name} ({prefix}, {columns}, {CREATED}{suffix})")
    TABLES.append(name)


def create_tables() -> None:
    table(
        "core.app_user",
        "login_id varchar(100) NOT NULL, password_hash varchar(255) NOT NULL, display_name varchar(100) NOT NULL, disabled_at timestamptz",
        scoped=False,
        after="status varchar(24) NOT NULL DEFAULT 'active'",
    )
    table(
        "core.auth_session",
        "user_id bigint NOT NULL, token_hash varchar(64) NOT NULL, csrf_token_hash varchar(64) NOT NULL, expires_at timestamptz NOT NULL, revoked_at timestamptz",
        scoped=False,
    )
    table(
        "core.role",
        "role_key varchar(40) NOT NULL, description varchar(200) NOT NULL",
        scoped=False,
    )
    table(
        "core.user_role",
        "user_id bigint NOT NULL, role_id bigint NOT NULL",
        scoped=False,
    )
    table(
        "core.workspace",
        "owner_user_id bigint, active_generation_id bigint, config_version bigint NOT NULL DEFAULT 1, energy_input_revision bigint NOT NULL DEFAULT 0",
        scoped=False,
        after="workspace_kind varchar(20) NOT NULL DEFAULT 'MEMBER', guest_session_key varchar(128), expires_at timestamptz, guest_actor_key uuid",
    )
    table(
        "core.data_generation",
        "workspace_id bigint NOT NULL, seed_version varchar(40) NOT NULL, seed_date date NOT NULL, activated_at timestamptz, retired_at timestamptz, purged_at timestamptz",
        scoped=False,
        after="status varchar(24) NOT NULL DEFAULT 'preparing'",
    )
    table(
        "core.workspace_module",
        "workspace_id bigint NOT NULL, module_key varchar(20) NOT NULL, enabled boolean NOT NULL DEFAULT true, updated_at timestamptz",
        scoped=False,
    )
    table(
        "core.job_run",
        "workspace_id bigint, job_kind varchar(40) NOT NULL, module_key varchar(20) NOT NULL, run_key varchar(100) NOT NULL, attempt_no integer NOT NULL DEFAULT 1, owner_token varchar(64) NOT NULL, heartbeat_at timestamptz, lease_expires_at timestamptz, target_generation_id bigint, started_at timestamptz NOT NULL, finished_at timestamptz, cleanup_status varchar(24) NOT NULL DEFAULT 'not_required', error_code varchar(64), error_summary varchar(500)",
        scoped=False,
        after="status varchar(24) NOT NULL DEFAULT 'running', scope_kind varchar(12) NOT NULL DEFAULT 'WORKSPACE', workspace_snapshot_id bigint, generation_snapshot_id bigint",
    )
    table(
        "core.audit_event",
        "workspace_id bigint, actor_user_id bigint, job_run_id bigint, action varchar(80) NOT NULL, entity_kind varchar(80) NOT NULL, entity_key varchar(150) NOT NULL, summary jsonb NOT NULL DEFAULT '{}'::jsonb, reason varchar(300)",
        scoped=False,
        after="actor_kind varchar(10) NOT NULL, actor_key varchar(100) NOT NULL, scope_kind varchar(12) NOT NULL DEFAULT 'WORKSPACE', workspace_snapshot_id bigint",
    )
    table(
        "core.request_receipt",
        "actor_user_id bigint, operation_key varchar(60) NOT NULL, request_key varchar(100) NOT NULL, request_hash varchar(64) NOT NULL, entity_kind varchar(60) NOT NULL, entity_id bigint NOT NULL, response_summary jsonb NOT NULL DEFAULT '{}'::jsonb, http_status integer NOT NULL, completed_at timestamptz NOT NULL",
        after="actor_kind varchar(10) NOT NULL, actor_key varchar(100) NOT NULL",
    )
    for schema in ("mes", "fems"):
        table(
            f"{schema}.site",
            "site_code varchar(30) NOT NULL, name varchar(100) NOT NULL, timezone varchar(60) NOT NULL DEFAULT 'Asia/Seoul'",
        )
        table(
            f"{schema}.location",
            "site_id bigint NOT NULL, parent_location_id bigint, location_code varchar(30) NOT NULL, name varchar(100) NOT NULL, kind varchar(20) NOT NULL",
        )
        table(
            f"{schema}.equipment",
            "location_id bigint NOT NULL, equipment_code varchar(30) NOT NULL, name varchar(100) NOT NULL, equipment_type varchar(40) NOT NULL, is_active boolean NOT NULL DEFAULT true",
        )
    for schema in ("mes", "erp"):
        table(
            f"{schema}.item",
            "item_code varchar(40) NOT NULL, name varchar(100) NOT NULL, base_unit varchar(10) NOT NULL DEFAULT 'EA', item_type varchar(20) NOT NULL DEFAULT 'finished', is_active boolean NOT NULL DEFAULT true",
            after="tax_category varchar(20) NOT NULL" if schema == "erp" else "",
        )
        table(
            f"{schema}.item_unit_conversion",
            "item_id bigint NOT NULL, from_unit varchar(10) NOT NULL, to_unit varchar(10) NOT NULL, factor numeric(18,6) NOT NULL",
        )
    table(
        "mes.process",
        "process_code varchar(30) NOT NULL, name varchar(100) NOT NULL, process_type varchar(20) NOT NULL, is_active boolean NOT NULL DEFAULT true",
    )
    table(
        "mes.process_equipment",
        "process_id bigint NOT NULL, equipment_id bigint NOT NULL",
    )
    table(
        "mes.route_version",
        "item_id bigint NOT NULL, route_code varchar(40) NOT NULL, version integer NOT NULL, published_at timestamptz, retired_at timestamptz",
        after="status varchar(24) NOT NULL DEFAULT 'draft'",
    )
    table(
        "mes.route_step",
        "route_version_id bigint NOT NULL, process_id bigint NOT NULL, sequence_no integer NOT NULL",
    )
    table(
        "mes.work_order",
        "order_no varchar(40) NOT NULL, item_id bigint NOT NULL, route_version_id bigint NOT NULL, plan_qty numeric(15,3) NOT NULL, unit varchar(10) NOT NULL, plan_start_date date NOT NULL, plan_end_date date NOT NULL, released_at timestamptz, started_at timestamptz, completed_at timestamptz, completion_reason varchar(24), cancel_reason varchar(300)",
        after="status varchar(24) NOT NULL DEFAULT 'draft', order_type varchar(10) NOT NULL DEFAULT 'STOCK', sales_order_line_id bigint, production_plan_line_id bigint NOT NULL, bom_version_id bigint",
    )
    table(
        "mes.lot",
        "lot_no varchar(50) NOT NULL, work_order_id bigint NOT NULL, route_version_id bigint NOT NULL, unit varchar(10) NOT NULL, completion_reason varchar(24)",
        after="status varchar(24) NOT NULL DEFAULT 'ready'",
    )
    table(
        "mes.operation_execution",
        "lot_id bigint NOT NULL, route_version_id bigint NOT NULL, route_step_id bigint NOT NULL, equipment_id bigint NOT NULL, unit varchar(10) NOT NULL, started_at timestamptz NOT NULL, ended_at timestamptz",
        after="status varchar(24) NOT NULL DEFAULT 'running'",
    )
    table(
        "mes.operation_result",
        "execution_id bigint NOT NULL, input_qty numeric(15,3) NOT NULL, output_qty numeric(15,3) NOT NULL, good_qty numeric(15,3) NOT NULL, defect_qty numeric(15,3) NOT NULL, unit varchar(10) NOT NULL, defect_reason varchar(300), confirmed_at timestamptz NOT NULL",
    )
    table(
        "mes.production_plan",
        "plan_code varchar(40) NOT NULL, target_month varchar(7) NOT NULL, sales_plan_code varchar(40), status varchar(20) NOT NULL DEFAULT 'draft'",
    )
    table(
        "mes.production_plan_line",
        "production_plan_id bigint NOT NULL, item_id bigint NOT NULL, target_week varchar(8) NOT NULL, plan_qty numeric(18,3) NOT NULL, unit varchar(10) NOT NULL",
    )
    table(
        "mes.packing_unit",
        "packing_no varchar(40) NOT NULL, packing_kind varchar(10) NOT NULL, parent_packing_unit_id bigint, status varchar(20) NOT NULL DEFAULT 'open'",
    )
    table(
        "mes.packing_member",
        "packing_unit_id bigint NOT NULL, lot_id bigint NOT NULL, packed_qty numeric(18,3) NOT NULL",
    )
    table(
        "mes.finished_goods_receipt",
        "packing_unit_id bigint NOT NULL, received_at timestamptz NOT NULL, status varchar(20) NOT NULL DEFAULT 'confirmed'",
    )
    table(
        "mes.bom_version",
        "bom_code varchar(40) NOT NULL, item_id bigint NOT NULL, version_no integer NOT NULL DEFAULT 1, status varchar(20) NOT NULL DEFAULT 'draft', published_at timestamptz",
    )
    table(
        "mes.bom_line",
        "bom_version_id bigint NOT NULL, line_no integer NOT NULL, material_item_id bigint NOT NULL, qty_per_unit numeric(18,3) NOT NULL, unit varchar(10) NOT NULL, loss_rate numeric(5,2) NOT NULL DEFAULT 0",
    )
    table(
        "mes.material_issue",
        "execution_id bigint NOT NULL, material_item_id bigint NOT NULL, material_lot_id bigint, bom_version_id bigint, issued_qty numeric(18,3) NOT NULL, unit varchar(10) NOT NULL, issued_at timestamptz NOT NULL",
    )
    table(
        "fems.meter",
        "site_id bigint NOT NULL, location_id bigint NOT NULL, parent_meter_id bigint, equipment_id bigint, meter_code varchar(40) NOT NULL, name varchar(100) NOT NULL, scope_kind varchar(20) NOT NULL",
    )
    table(
        "fems.energy_reading",
        "meter_channel_id bigint NOT NULL, observed_at timestamptz NOT NULL, period_start timestamptz, value numeric(20,6) NOT NULL, unit varchar(10) NOT NULL, quality varchar(20) NOT NULL DEFAULT 'valid', source_key varchar(100) NOT NULL, input_revision bigint NOT NULL",
    )
    table(
        "fems.energy_allocation",
        "meter_channel_id bigint NOT NULL, period_start timestamptz NOT NULL, period_end timestamptz NOT NULL, quantity numeric(20,6) NOT NULL, unit varchar(10) NOT NULL, method_key varchar(40) NOT NULL, method_version integer NOT NULL, input_revision bigint NOT NULL, quality varchar(20) NOT NULL, basis jsonb NOT NULL DEFAULT '{}'::jsonb",
        after="equipment_id bigint NOT NULL",
    )
    table(
        "fems.energy_source",
        "source_code varchar(20) NOT NULL, name varchar(50) NOT NULL, source_kind varchar(20) NOT NULL, measure_unit varchar(10) NOT NULL, is_billable boolean NOT NULL DEFAULT true, is_active boolean NOT NULL DEFAULT true",
    )
    table(
        "fems.meter_channel",
        "meter_id bigint NOT NULL, energy_source_id bigint NOT NULL, channel_code varchar(20) NOT NULL, name varchar(50) NOT NULL, measurement_kind varchar(20) NOT NULL, unit varchar(10) NOT NULL, multiplier numeric(18,6) NOT NULL DEFAULT 1, is_active boolean NOT NULL DEFAULT true",
    )
    table(
        "fems.energy_factor",
        "energy_source_id bigint NOT NULL, factor_kind varchar(20) NOT NULL, effective_year varchar(4) NOT NULL, factor_value numeric(18,6) NOT NULL, factor_unit varchar(20) NOT NULL, source_note varchar(200) NOT NULL",
    )
    table(
        "fems.tariff",
        "energy_source_id bigint NOT NULL, tariff_code varchar(30) NOT NULL, name varchar(100) NOT NULL, contract_type varchar(50), basic_charge numeric(18,4) NOT NULL DEFAULT 0, usage_rate numeric(18,4) NOT NULL, currency varchar(3) NOT NULL DEFAULT 'KRW', effective_from varchar(7) NOT NULL, effective_to varchar(7)",
    )
    table(
        "fems.energy_target",
        "site_id bigint, equipment_id bigint, energy_source_id bigint, target_scope varchar(20) NOT NULL, target_month varchar(7) NOT NULL, target_value numeric(18,6) NOT NULL, unit varchar(10) NOT NULL",
    )
    table(
        "fems.energy_baseline",
        "baseline_code varchar(30) NOT NULL, baseline_scope varchar(20) NOT NULL, item_code varchar(40), equipment_id bigint, energy_source_id bigint, baseline_value numeric(18,6) NOT NULL, unit varchar(20) NOT NULL, period_from varchar(7) NOT NULL, period_to varchar(7) NOT NULL, status varchar(20) NOT NULL DEFAULT 'draft'",
    )
    table(
        "fems.production_record",
        "source_key varchar(100) NOT NULL, version_no integer NOT NULL DEFAULT 1, equipment_id bigint NOT NULL, item_code varchar(40) NOT NULL, period_start timestamptz NOT NULL, period_end timestamptz NOT NULL, production_qty numeric(18,3) NOT NULL, unit varchar(10) NOT NULL, status varchar(20) NOT NULL DEFAULT 'draft', confirmed_at timestamptz",
    )
    table(
        "erp.partner",
        "partner_code varchar(40) NOT NULL, partner_name varchar(200) NOT NULL, partner_kind varchar(20) NOT NULL, is_active boolean NOT NULL DEFAULT true",
        after="payment_term_days integer",
    )
    table(
        "erp.sales_plan",
        "plan_code varchar(40) NOT NULL, target_month varchar(7) NOT NULL, status varchar(20) NOT NULL DEFAULT 'draft', confirmed_at timestamptz",
    )
    table(
        "erp.sales_plan_line",
        "sales_plan_id bigint NOT NULL, item_id bigint NOT NULL, plan_qty numeric(18,3) NOT NULL, unit varchar(10) NOT NULL",
    )
    table(
        "erp.sales_order",
        "order_no varchar(40) NOT NULL, partner_id bigint NOT NULL, ordered_on date NOT NULL, due_on date NOT NULL, status varchar(20) NOT NULL DEFAULT 'open'",
        after="quotation_id bigint",
    )
    table(
        "erp.sales_order_line",
        "sales_order_id bigint NOT NULL, line_no integer NOT NULL, item_id bigint NOT NULL, order_qty numeric(18,3) NOT NULL, unit varchar(10) NOT NULL, unit_price numeric(18,4) NOT NULL",
    )
    table(
        "erp.shipment_order",
        "ship_order_no varchar(40) NOT NULL, sales_order_id bigint NOT NULL, ordered_on date NOT NULL, status varchar(20) NOT NULL DEFAULT 'open'",
        after="cancel_reason varchar(300)",
    )
    table(
        "erp.shipment_order_line",
        "shipment_order_id bigint NOT NULL, sales_order_line_id bigint NOT NULL, order_qty numeric(18,3) NOT NULL",
        after="sales_order_id bigint NOT NULL",
    )
    table(
        "erp.shipment",
        "shipment_no varchar(40) NOT NULL, shipment_order_id bigint NOT NULL, shipped_at timestamptz NOT NULL, status varchar(20) NOT NULL DEFAULT 'draft'",
    )
    table(
        "erp.shipment_line",
        "shipment_id bigint NOT NULL, shipment_order_line_id bigint NOT NULL, packing_no varchar(40), shipped_qty numeric(18,3) NOT NULL",
        after="shipment_order_id bigint NOT NULL, item_id bigint NOT NULL, shipped_uom varchar(10) NOT NULL",
    )
    table(
        "erp.sales_record",
        "shipment_id bigint NOT NULL, partner_id bigint NOT NULL, supply_amount numeric(18,2) NOT NULL, tax_amount numeric(18,2) NOT NULL, total_amount numeric(18,2) NOT NULL, recognized_at timestamptz NOT NULL",
        after="currency varchar(3) NOT NULL DEFAULT 'KRW', cancelled_at timestamptz, cancel_reason varchar(300)",
    )
    table(
        "erp.quotation",
        "quote_no varchar(40) NOT NULL, revision_no integer NOT NULL DEFAULT 1, partner_id bigint NOT NULL, quoted_on date NOT NULL, valid_until date, status varchar(20) NOT NULL DEFAULT 'draft', remark text",
    )
    table(
        "erp.quotation_line",
        "quotation_id bigint NOT NULL, line_no integer NOT NULL, item_id bigint NOT NULL, quote_qty numeric(18,3) NOT NULL, unit varchar(10) NOT NULL, unit_price numeric(18,4) NOT NULL, discount_rate numeric(5,2) NOT NULL DEFAULT 0",
    )
    table(
        "erp.quotation_status_history",
        "quotation_id bigint NOT NULL, status varchar(20) NOT NULL, changed_at timestamptz NOT NULL, reason varchar(200)",
    )
    table(
        "erp.partner_item_price",
        "partner_id bigint NOT NULL, item_id bigint NOT NULL, price_kind varchar(20) NOT NULL DEFAULT 'SALE', unit_price numeric(18,4) NOT NULL, currency varchar(3) NOT NULL DEFAULT 'KRW', effective_from varchar(7) NOT NULL, effective_to varchar(7), is_active boolean NOT NULL DEFAULT true",
    )
    table(
        "erp.purchase_invoice",
        "invoice_no varchar(40) NOT NULL, partner_id bigint NOT NULL, invoice_date date NOT NULL, due_date date, currency varchar(3) NOT NULL DEFAULT 'KRW', supply_amount numeric(18,2) NOT NULL DEFAULT 0, tax_amount numeric(18,2) NOT NULL DEFAULT 0, total_amount numeric(18,2) NOT NULL DEFAULT 0, status varchar(20) NOT NULL DEFAULT 'draft', confirmed_at timestamptz, cancelled_at timestamptz, cancel_reason varchar(300)",
    )
    table(
        "erp.purchase_invoice_line",
        "purchase_invoice_id bigint NOT NULL, line_no integer NOT NULL, item_id bigint NOT NULL, quantity numeric(18,3) NOT NULL, unit varchar(10) NOT NULL, unit_price numeric(18,4) NOT NULL, currency varchar(3) NOT NULL DEFAULT 'KRW', supply_amount numeric(18,2) NOT NULL, tax_amount numeric(18,2) NOT NULL, total_amount numeric(18,2) NOT NULL",
    )
    for name, source in (
        ("receivable", "sales_record"),
        ("payable", "purchase_invoice"),
    ):
        table(
            f"erp.{name}",
            f"{source}_id bigint NOT NULL, partner_id bigint NOT NULL, amount numeric(18,2) NOT NULL, currency varchar(3) NOT NULL DEFAULT 'KRW', due_date date",
        )
    for name, date in (("receipt", "received_on"), ("payment", "paid_on")):
        table(
            f"erp.{name}",
            f"{name}_no varchar(40) NOT NULL, partner_id bigint NOT NULL, {date} date NOT NULL, amount numeric(18,2) NOT NULL, currency varchar(3) NOT NULL DEFAULT 'KRW', status varchar(20) NOT NULL DEFAULT 'draft', confirmed_at timestamptz",
        )
    for name, source in (("receipt", "receivable"), ("payment", "payable")):
        table(
            f"erp.{name}_apply",
            f"{name}_id bigint NOT NULL, {source}_id bigint NOT NULL, partner_id bigint NOT NULL, currency varchar(3) NOT NULL DEFAULT 'KRW', amount numeric(18,2) NOT NULL, apply_key varchar(100) NOT NULL, applied_at timestamptz NOT NULL",
        )
    table(
        "erp.tax_invoice",
        "sales_record_id bigint NOT NULL, partner_id bigint NOT NULL, currency varchar(3) NOT NULL DEFAULT 'KRW', status varchar(20) NOT NULL DEFAULT 'pending', approval_no varchar(60), issued_on date",
    )
    table(
        "erp.account",
        "account_code varchar(40) NOT NULL, account_name varchar(100) NOT NULL",
    )
    table(
        "erp.posting_rule",
        "transaction_kind varchar(20) NOT NULL, line_no integer NOT NULL, entry_side varchar(6) NOT NULL, account_id bigint NOT NULL, account_code varchar(40) NOT NULL, amount_basis varchar(10) NOT NULL",
    )


# C 번호·테이블·컬럼. S는 명시된 복합 범위 키의 축약이다.
KEYS = """
1 core.app_user login_id
4 core.auth_session token_hash
7 core.role role_key
9 core.user_role user_id,role_id
11 core.workspace owner_user_id
15 core.data_generation workspace_id,id
20 core.workspace_module workspace_id,id
21 core.workspace_module workspace_id,module_key
25 core.job_run workspace_id,id
26 core.job_run workspace_id,job_kind,run_key,attempt_no
33 core.audit_event workspace_id,id
38 mes.site S,site_code
39 fems.site S,site_code
44 mes.location S,site_id,location_code
45 fems.location S,site_id,location_code
46 mes.location S,id,site_id
47 fems.location S,id,site_id
56 mes.equipment S,equipment_code
57 fems.equipment S,equipment_code
58 mes.equipment S,id,location_id
59 fems.equipment S,id,location_id
64 mes.item S,item_code
65 erp.item S,item_code
66 mes.item S,id,base_unit
67 erp.item S,id,base_unit
76 mes.item_unit_conversion S,item_id,from_unit
77 erp.item_unit_conversion S,item_id,from_unit
84 mes.process S,process_code
87 mes.process_equipment S,process_id,equipment_id
90 mes.route_version S,route_code,version
91 mes.route_version S,id,item_id
96 mes.route_step S,route_version_id,sequence_no
97 mes.route_step S,id,route_version_id
101 mes.work_order S,order_no
102 mes.work_order S,id,route_version_id
103 mes.work_order S,id,route_version_id,unit
111 mes.lot S,lot_no
112 mes.lot S,work_order_id
113 mes.lot S,id,route_version_id
114 mes.lot S,id,route_version_id,unit
119 mes.operation_execution S,lot_id,route_step_id
120 mes.operation_execution S,id,unit
125 mes.operation_result S,execution_id
136 fems.meter S,meter_code
137 fems.meter S,id,site_id
142 fems.energy_reading S,meter_channel_id,source_key
209 erp.partner S,partner_code
213 erp.sales_plan S,plan_code
218 erp.sales_plan_line S,sales_plan_id,item_id
222 erp.sales_order S,order_no
226 erp.sales_order_line S,sales_order_id,line_no
230 erp.shipment_order S,ship_order_no
233 erp.shipment_order_line S,shipment_order_id,sales_order_line_id
238 erp.shipment S,shipment_no
239 erp.shipment S,shipment_order_id
247 erp.sales_record S,shipment_id
252 mes.production_plan S,plan_code
256 mes.production_plan_line S,production_plan_id,item_id,target_week
260 mes.packing_unit S,packing_no
266 mes.packing_member S,packing_unit_id,lot_id
271 mes.finished_goods_receipt S,packing_unit_id
280 core.workspace guest_actor_key
288 core.request_receipt S,actor_kind,actor_key,operation_key,request_key
297 mes.production_plan_line S,id,item_id,unit
308 erp.shipment_order S,id,sales_order_id
309 erp.sales_order_line S,id,sales_order_id
310 erp.shipment S,id,shipment_order_id
311 erp.shipment_order_line S,id,shipment_order_id
314 fems.energy_source S,source_code
318 fems.meter_channel S,meter_id,channel_code
319 fems.meter_channel S,id,unit
326 fems.energy_factor S,energy_source_id,factor_kind,effective_year
334 fems.tariff S,energy_source_id,tariff_code,effective_from
340 fems.energy_target S,target_scope,site_id,equipment_id,energy_source_id,target_month
346 fems.energy_baseline S,baseline_code
354 erp.quotation S,quote_no,revision_no
360 erp.quotation_line S,quotation_id,line_no
368 erp.partner_item_price S,partner_id,item_id,price_kind,effective_from
372 fems.energy_allocation S,equipment_id,meter_channel_id,period_start,period_end,method_key,method_version
375 mes.bom_version S,bom_code
376 mes.bom_version S,item_id,version_no
382 mes.bom_line S,bom_version_id,line_no
383 mes.bom_line S,bom_version_id,material_item_id
389 mes.material_issue S,execution_id,material_item_id,material_lot_id
401 fems.production_record S,source_key,version_no
415 erp.sales_record S,id,partner_id,currency
424 erp.purchase_invoice S,invoice_no
425 erp.purchase_invoice S,id,partner_id,currency
426 erp.purchase_invoice S,id,currency
433 erp.purchase_invoice_line S,purchase_invoice_id,line_no
439 erp.receivable S,sales_record_id
440 erp.receivable S,id,partner_id,currency
447 erp.payable S,purchase_invoice_id
448 erp.payable S,id,partner_id,currency
455 erp.receipt S,receipt_no
456 erp.receipt S,id,partner_id,currency
463 erp.receipt_apply S,apply_key
476 erp.payment S,payment_no
477 erp.payment S,id,partner_id,currency
484 erp.payment_apply S,apply_key
497 erp.tax_invoice S,sales_record_id
503 erp.account S,account_code
504 erp.account S,id,account_code
509 erp.posting_rule S,transaction_kind,line_no
"""
INDEXES = """
173 core.auth_session expires_at
174 core.audit_event workspace_id,created_at
175 core.job_run workspace_id,status,lease_expires_at
176 mes.work_order S,status,created_at
177 mes.operation_execution S,equipment_id,started_at
178 fems.energy_reading S,meter_channel_id,observed_at
179 core.auth_session user_id
180 core.user_role role_id
181 core.workspace id,active_generation_id
182 core.job_run workspace_id,target_generation_id
183 core.audit_event actor_user_id
184 core.audit_event workspace_id,job_run_id
185 mes.location S,parent_location_id,site_id
186 fems.location S,parent_location_id,site_id
187 mes.equipment S,location_id
188 fems.equipment S,location_id
189 mes.item_unit_conversion S,item_id,to_unit
190 erp.item_unit_conversion S,item_id,to_unit
191 mes.process_equipment S,equipment_id
192 mes.route_version S,item_id
193 mes.route_step S,process_id
194 mes.work_order S,item_id,unit
195 mes.work_order S,route_version_id,item_id
196 mes.lot S,work_order_id,route_version_id,unit
197 mes.operation_execution S,lot_id,route_version_id,unit
198 mes.operation_execution S,route_step_id,route_version_id
199 mes.operation_result S,execution_id,unit
200 core.request_receipt actor_user_id
201 fems.meter S,site_id
202 fems.meter S,location_id,site_id
203 fems.meter S,parent_meter_id,site_id
204 fems.meter S,equipment_id,location_id
205 fems.energy_reading S,meter_channel_id,unit
206 fems.energy_allocation S,meter_channel_id,unit
466 erp.receipt_apply S,receivable_id
467 erp.receipt_apply S,receipt_id
487 erp.payment_apply S,payable_id
488 erp.payment_apply S,payment_id
"""
PARTIALS = """
17 core.data_generation workspace_id | status = 'active'
31 core.job_run workspace_id,job_kind,run_key | status = 'succeeded'
242 erp.shipment_line S,shipment_id,packing_no | packing_no IS NOT NULL
243 erp.shipment_line S,packing_no | packing_no IS NOT NULL
273 core.workspace owner_user_id | workspace_kind = 'MEMBER'
274 core.workspace guest_session_key | workspace_kind = 'GUEST'
295 core.job_run job_kind,run_key,attempt_no | scope_kind = 'GLOBAL'
498 erp.tax_invoice S,approval_no | approval_no IS NOT NULL
"""
FKS = """
0 core.auth_session user_id core.app_user id
1 core.user_role user_id core.app_user id
2 core.user_role role_id core.role id
3 core.workspace owner_user_id core.app_user id
4 core.data_generation workspace_id core.workspace id
5 core.workspace id,active_generation_id core.data_generation workspace_id,id
6 core.workspace_module workspace_id core.workspace id
7 core.job_run workspace_id core.workspace id
8 core.job_run workspace_id,target_generation_id core.data_generation workspace_id,id
9 core.audit_event workspace_id core.workspace id
10 core.audit_event actor_user_id core.app_user id
11 core.audit_event workspace_id,job_run_id core.job_run workspace_id,id
16 mes.location S,site_id mes.site S,id
17 fems.location S,site_id fems.site S,id
18 mes.location S,parent_location_id,site_id mes.location S,id,site_id
19 fems.location S,parent_location_id,site_id fems.location S,id,site_id
22 mes.equipment S,location_id mes.location S,id
23 fems.equipment S,location_id fems.location S,id
28 mes.item_unit_conversion S,item_id,to_unit mes.item S,id,base_unit
29 erp.item_unit_conversion S,item_id,to_unit erp.item S,id,base_unit
32 mes.process_equipment S,process_id mes.process S,id
33 mes.process_equipment S,equipment_id mes.equipment S,id
35 mes.route_version S,item_id mes.item S,id
37 mes.route_step S,route_version_id mes.route_version S,id
38 mes.route_step S,process_id mes.process S,id
40 mes.work_order S,item_id,unit mes.item S,id,base_unit
41 mes.work_order S,route_version_id,item_id mes.route_version S,id,item_id
43 mes.lot S,work_order_id,route_version_id,unit mes.work_order S,id,route_version_id,unit
45 mes.operation_execution S,lot_id,route_version_id,unit mes.lot S,id,route_version_id,unit
46 mes.operation_execution S,route_step_id,route_version_id mes.route_step S,id,route_version_id
47 mes.operation_execution S,equipment_id mes.equipment S,id
49 mes.operation_result S,execution_id,unit mes.operation_execution S,id,unit
51 core.request_receipt actor_user_id core.app_user id
53 fems.meter S,site_id fems.site S,id
54 fems.meter S,location_id,site_id fems.location S,id,site_id
55 fems.meter S,parent_meter_id,site_id fems.meter S,id,site_id
56 fems.meter S,equipment_id,location_id fems.equipment S,id,location_id
58 fems.energy_reading S,meter_channel_id,unit fems.meter_channel S,id,unit
60 fems.energy_allocation S,meter_channel_id,unit fems.meter_channel S,id,unit
64 erp.sales_plan_line S,sales_plan_id erp.sales_plan S,id
65 erp.sales_plan_line S,item_id erp.item S,id
67 erp.sales_order S,partner_id erp.partner S,id
69 erp.sales_order_line S,sales_order_id erp.sales_order S,id
70 erp.sales_order_line S,item_id erp.item S,id
72 erp.shipment_order S,sales_order_id erp.sales_order S,id
75 erp.shipment S,shipment_order_id erp.shipment_order S,id
78 erp.sales_record S,shipment_id erp.shipment S,id
79 erp.sales_record S,partner_id erp.partner S,id
82 mes.production_plan_line S,production_plan_id mes.production_plan S,id
83 mes.production_plan_line S,item_id mes.item S,id
85 mes.packing_unit S,parent_packing_unit_id mes.packing_unit S,id
87 mes.packing_member S,packing_unit_id mes.packing_unit S,id
88 mes.packing_member S,lot_id mes.lot S,id
90 mes.finished_goods_receipt S,packing_unit_id mes.packing_unit S,id
91 mes.work_order S,production_plan_line_id,item_id,unit mes.production_plan_line S,id,item_id,unit
92 erp.shipment_order_line S,shipment_order_id,sales_order_id erp.shipment_order S,id,sales_order_id
93 erp.shipment_order_line S,sales_order_line_id,sales_order_id erp.sales_order_line S,id,sales_order_id
94 erp.shipment_line S,shipment_id,shipment_order_id erp.shipment S,id,shipment_order_id
95 erp.shipment_line S,shipment_order_line_id,shipment_order_id erp.shipment_order_line S,id,shipment_order_id
98 fems.meter_channel S,meter_id fems.meter S,id
99 fems.meter_channel S,energy_source_id fems.energy_source S,id
101 fems.energy_factor S,energy_source_id fems.energy_source S,id
103 fems.tariff S,energy_source_id fems.energy_source S,id
105 fems.energy_target S,site_id fems.site S,id
106 fems.energy_target S,equipment_id fems.equipment S,id
107 fems.energy_target S,energy_source_id fems.energy_source S,id
109 fems.energy_baseline S,equipment_id fems.equipment S,id
110 fems.energy_baseline S,energy_source_id fems.energy_source S,id
112 erp.quotation S,partner_id erp.partner S,id
114 erp.quotation_line S,quotation_id erp.quotation S,id
115 erp.quotation_line S,item_id erp.item S,id
117 erp.quotation_status_history S,quotation_id erp.quotation S,id
119 erp.partner_item_price S,partner_id erp.partner S,id
120 erp.partner_item_price S,item_id erp.item S,id
121 erp.sales_order S,quotation_id erp.quotation S,id
122 erp.shipment_line S,item_id erp.item S,id
123 fems.energy_allocation S,equipment_id fems.equipment S,id
125 mes.bom_version S,item_id mes.item S,id
127 mes.bom_line S,bom_version_id mes.bom_version S,id
128 mes.bom_line S,material_item_id mes.item S,id
130 mes.material_issue S,execution_id mes.operation_execution S,id
131 mes.material_issue S,material_item_id mes.item S,id
132 mes.material_issue S,material_lot_id mes.lot S,id
133 mes.material_issue S,bom_version_id mes.bom_version S,id
134 mes.work_order S,bom_version_id mes.bom_version S,id
136 fems.production_record S,equipment_id fems.equipment S,id
138 erp.purchase_invoice S,partner_id erp.partner S,id
140 erp.purchase_invoice_line S,purchase_invoice_id,currency erp.purchase_invoice S,id,currency
141 erp.purchase_invoice_line S,item_id erp.item S,id
143 erp.receivable S,sales_record_id,partner_id,currency erp.sales_record S,id,partner_id,currency
145 erp.payable S,purchase_invoice_id,partner_id,currency erp.purchase_invoice S,id,partner_id,currency
147 erp.receipt S,partner_id erp.partner S,id
149 erp.receipt_apply S,receivable_id,partner_id,currency erp.receivable S,id,partner_id,currency
150 erp.receipt_apply S,receipt_id,partner_id,currency erp.receipt S,id,partner_id,currency
152 erp.payment S,partner_id erp.partner S,id
154 erp.payment_apply S,payable_id,partner_id,currency erp.payable S,id,partner_id,currency
155 erp.payment_apply S,payment_id,partner_id,currency erp.payment S,id,partner_id,currency
157 erp.tax_invoice S,sales_record_id,partner_id,currency erp.sales_record S,id,partner_id,currency
160 erp.posting_rule S,account_id,account_code erp.account S,id,account_code
"""
CHECKS = """
2 core.app_user status IN ('active', 'disabled')
5 core.auth_session expires_at > created_at
12 core.workspace config_version > 0
13 core.workspace energy_input_revision >= 0
16 core.data_generation status IN ('preparing', 'ready', 'active', 'retired', 'purged', 'failed')
22 core.workspace_module module_key IN ('core','mes','erp','fems')
23 core.workspace_module module_key <> 'core' OR enabled
27 core.job_run attempt_no > 0
28 core.job_run cleanup_status IN ('not_required','pending','running','succeeded','failed')
29 core.job_run finished_at IS NULL OR finished_at >= started_at
30 core.job_run status IN ('running', 'succeeded', 'failed')
48 mes.location kind IN ('building','zone','workcenter')
49 fems.location kind IN ('building','zone','workcenter')
50 mes.location parent_location_id IS NULL OR parent_location_id <> id
51 fems.location parent_location_id IS NULL OR parent_location_id <> id
68 mes.item base_unit IN ('EA','BOX','KG','M','L','SET')
69 erp.item base_unit IN ('EA','BOX','KG','M','L','SET')
70 mes.item item_type IN ('finished','semi_finished','raw','auxiliary')
71 erp.item item_type IN ('finished','semi_finished','raw','auxiliary')
78 mes.item_unit_conversion factor > 0
79 erp.item_unit_conversion factor > 0
80 mes.item_unit_conversion from_unit <> to_unit
81 erp.item_unit_conversion from_unit <> to_unit
92 mes.route_version version > 0
93 mes.route_version status IN ('draft', 'published', 'retired')
98 mes.route_step sequence_no > 0
104 mes.work_order plan_qty > 0
105 mes.work_order unit <> 'EA' OR plan_qty = trunc(plan_qty)
106 mes.work_order plan_end_date >= plan_start_date
107 mes.work_order completion_reason IS NULL OR completion_reason IN ('normal','all_defective')
108 mes.work_order status IN ('draft', 'released', 'in_progress', 'completed', 'cancelled')
115 mes.lot completion_reason IS NULL OR completion_reason IN ('normal','all_defective')
116 mes.lot status IN ('ready', 'in_progress', 'completed')
121 mes.operation_execution ended_at IS NULL OR ended_at >= started_at
122 mes.operation_execution status IN ('running', 'completed')
126 mes.operation_result input_qty > 0
127 mes.operation_result good_qty >= 0 AND defect_qty >= 0
128 mes.operation_result input_qty = output_qty AND output_qty = good_qty + defect_qty
129 mes.operation_result unit <> 'EA' OR (input_qty = trunc(input_qty) AND good_qty = trunc(good_qty) AND defect_qty = trunc(defect_qty))
130 mes.operation_result defect_qty = 0 OR (defect_reason IS NOT NULL AND length(trim(defect_reason)) > 0)
133 core.request_receipt http_status BETWEEN 200 AND 299
138 fems.meter scope_kind IN ('factory','site_total')
139 fems.meter parent_meter_id IS NULL OR parent_meter_id <> id
143 fems.energy_reading value >= 0
144 fems.energy_reading input_revision >= 0
145 fems.energy_reading period_start IS NULL OR period_start < observed_at
146 fems.energy_reading quality IN ('valid','estimated','reset','invalid')
149 fems.energy_allocation period_end > period_start
150 fems.energy_allocation quantity >= 0
151 fems.energy_allocation method_version > 0
152 fems.energy_allocation input_revision >= 0
153 fems.energy_allocation quality IN ('valid','estimated','invalid')
154 mes.operation_execution (status = 'running' AND ended_at IS NULL) OR (status = 'completed' AND ended_at IS NOT NULL)
155 mes.work_order (status = 'completed') = (completion_reason IS NOT NULL)
156 mes.lot (status = 'completed') = (completion_reason IS NOT NULL)
157 mes.work_order status <> 'cancelled' OR (cancel_reason IS NOT NULL AND length(trim(cancel_reason)) > 0)
158 mes.work_order (status = 'completed') = (completed_at IS NOT NULL)
159 mes.work_order status NOT IN ('released','in_progress','completed') OR released_at IS NOT NULL
160 mes.work_order status NOT IN ('in_progress','completed') OR started_at IS NOT NULL
161 mes.work_order completed_at IS NULL OR completed_at >= started_at
162 core.job_run (status = 'running' AND finished_at IS NULL) OR (status IN ('succeeded','failed') AND finished_at IS NOT NULL)
163 mes.route_version status = 'draft' OR published_at IS NOT NULL
164 mes.route_version status <> 'retired' OR retired_at IS NOT NULL
210 erp.partner partner_kind IN ('CUSTOMER','SUPPLIER')
214 erp.sales_plan target_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'
219 erp.sales_plan_line plan_qty >= 0
223 erp.sales_order due_on >= ordered_on
227 erp.sales_order_line order_qty > 0
234 erp.shipment_order_line order_qty > 0
244 erp.shipment_line shipped_qty > 0
248 erp.sales_record total_amount = supply_amount + tax_amount
253 mes.production_plan target_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'
257 mes.production_plan_line plan_qty >= 0
261 mes.packing_unit packing_kind IN ('BOX','PALLET')
262 mes.packing_unit parent_packing_unit_id IS NULL OR parent_packing_unit_id <> id
267 mes.packing_member packed_qty > 0
276 mes.work_order order_type = 'STOCK'
277 mes.work_order order_type = 'ORDER' OR sales_order_line_id IS NULL
278 core.workspace workspace_kind IN ('MEMBER','GUEST','TEMPLATE')
279 core.workspace (workspace_kind = 'MEMBER' AND owner_user_id IS NOT NULL AND guest_session_key IS NULL AND expires_at IS NULL AND guest_actor_key IS NULL) OR (workspace_kind = 'GUEST' AND owner_user_id IS NULL AND guest_session_key IS NOT NULL AND expires_at IS NOT NULL AND guest_actor_key IS NOT NULL) OR (workspace_kind = 'TEMPLATE' AND owner_user_id IS NULL AND guest_session_key IS NULL AND expires_at IS NULL AND guest_actor_key IS NULL)
282 core.request_receipt (actor_kind = 'MEMBER' AND actor_user_id IS NOT NULL) OR (actor_kind IN ('GUEST','SYSTEM') AND actor_user_id IS NULL)
283 core.request_receipt length(trim(actor_key)) > 0
285 core.audit_event (actor_kind = 'MEMBER' AND actor_user_id IS NOT NULL) OR (actor_kind IN ('GUEST','SYSTEM') AND actor_user_id IS NULL)
286 core.audit_event length(trim(actor_key)) > 0
289 core.audit_event (scope_kind = 'WORKSPACE' AND workspace_id IS NOT NULL AND workspace_snapshot_id IS NULL) OR (scope_kind = 'GLOBAL' AND workspace_id IS NULL AND workspace_snapshot_id IS NULL) OR (scope_kind = 'RETIRED' AND workspace_id IS NULL AND workspace_snapshot_id IS NOT NULL)
291 core.job_run (scope_kind = 'WORKSPACE' AND workspace_id IS NOT NULL AND workspace_snapshot_id IS NULL) OR (scope_kind = 'GLOBAL' AND workspace_id IS NULL AND workspace_snapshot_id IS NULL) OR (scope_kind = 'RETIRED' AND workspace_id IS NULL AND workspace_snapshot_id IS NOT NULL)
293 core.job_run workspace_id IS NOT NULL OR target_generation_id IS NULL
294 core.job_run scope_kind = 'RETIRED' OR generation_snapshot_id IS NULL
299 mes.packing_unit status IN ('open', 'closed', 'received', 'shipped')
300 mes.finished_goods_receipt status IN ('confirmed')
301 erp.shipment_order status IN ('open', 'shipped', 'cancelled')
302 erp.shipment_order (status = 'cancelled' AND cancel_reason IS NOT NULL AND length(trim(cancel_reason)) > 0) OR (status <> 'cancelled' AND cancel_reason IS NULL)
315 fems.energy_source source_kind IN ('ELECTRIC','FUEL','HEAT','UTILITY')
320 fems.meter_channel measurement_kind IN ('CUMULATIVE','INSTANT')
321 fems.meter_channel multiplier > 0
327 fems.energy_factor factor_kind IN ('PRIMARY','EMISSION')
328 fems.energy_factor effective_year ~ '^[0-9]{4}$'
329 fems.energy_factor factor_value > 0
335 fems.tariff effective_from ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'
336 fems.tariff usage_rate >= 0
341 fems.energy_target target_scope IN ('SITE','EQUIPMENT')
342 fems.energy_target (target_scope = 'SITE' AND site_id IS NOT NULL AND equipment_id IS NULL) OR (target_scope = 'EQUIPMENT' AND equipment_id IS NOT NULL)
343 fems.energy_target target_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'
347 fems.energy_baseline baseline_scope IN ('ITEM','EQUIPMENT')
348 fems.energy_baseline (baseline_scope = 'ITEM' AND item_code IS NOT NULL AND equipment_id IS NULL) OR (baseline_scope = 'EQUIPMENT' AND equipment_id IS NOT NULL AND item_code IS NULL)
349 fems.energy_baseline baseline_value > 0
355 erp.quotation revision_no >= 1
356 erp.quotation valid_until IS NULL OR valid_until >= quoted_on
361 erp.quotation_line quote_qty > 0
362 erp.quotation_line discount_rate >= 0 AND discount_rate <= 100
369 erp.partner_item_price unit_price >= 0
370 erp.partner_item_price effective_from ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'
377 mes.bom_version version_no >= 1
384 mes.bom_line qty_per_unit > 0
385 mes.bom_line loss_rate >= 0 AND loss_rate < 100
390 mes.material_issue issued_qty > 0
395 mes.production_plan sales_plan_code IS NULL OR length(btrim(sales_plan_code)) > 0
396 erp.shipment_line packing_no IS NULL OR length(btrim(packing_no)) > 0
397 fems.energy_baseline item_code IS NULL OR length(btrim(item_code)) > 0
402 fems.production_record period_end > period_start
403 fems.production_record production_qty >= 0
404 fems.production_record version_no >= 1
405 fems.production_record length(btrim(source_key)) > 0 AND length(btrim(item_code)) > 0 AND length(btrim(unit)) > 0
406 fems.production_record (status = 'draft' AND confirmed_at IS NULL) OR (status = 'confirmed' AND confirmed_at IS NOT NULL)
410 mes.production_plan_line target_week ~ '^[0-9]{4}-W(0[1-9]|[1-4][0-9]|5[0-3])$'
411 fems.tariff effective_to ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'
412 fems.energy_baseline period_from ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'
413 fems.energy_baseline period_to ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'
414 erp.partner_item_price effective_to ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'
416 erp.sales_record currency = 'KRW'
417 erp.sales_record supply_amount >= 0 AND tax_amount >= 0 AND total_amount >= 0
418 erp.sales_record (cancelled_at IS NULL AND cancel_reason IS NULL) OR (cancelled_at IS NOT NULL AND length(btrim(cancel_reason)) > 0 AND cancel_reason IS NOT NULL)
423 erp.purchase_invoice currency = 'KRW'
427 erp.purchase_invoice supply_amount >= 0 AND tax_amount >= 0 AND total_amount = supply_amount + tax_amount
428 erp.purchase_invoice (status = 'draft' AND confirmed_at IS NULL AND cancelled_at IS NULL AND cancel_reason IS NULL) OR (status = 'confirmed' AND confirmed_at IS NOT NULL AND cancelled_at IS NULL AND cancel_reason IS NULL) OR (status = 'cancelled' AND cancelled_at IS NOT NULL AND cancel_reason IS NOT NULL AND length(btrim(cancel_reason)) > 0)
432 erp.purchase_invoice_line currency = 'KRW'
434 erp.purchase_invoice_line line_no >= 1 AND quantity > 0 AND unit_price >= 0 AND supply_amount >= 0 AND tax_amount >= 0 AND total_amount = supply_amount + tax_amount
438 erp.receivable currency = 'KRW'
441 erp.receivable amount >= 0
446 erp.payable currency = 'KRW'
449 erp.payable amount >= 0
454 erp.receipt currency = 'KRW'
457 erp.receipt amount > 0
458 erp.receipt (status = 'draft' AND confirmed_at IS NULL) OR (status = 'confirmed' AND confirmed_at IS NOT NULL)
462 erp.receipt_apply currency = 'KRW'
464 erp.receipt_apply amount > 0
465 erp.receipt_apply length(btrim(apply_key)) > 0
475 erp.payment currency = 'KRW'
478 erp.payment amount > 0
479 erp.payment (status = 'draft' AND confirmed_at IS NULL) OR (status = 'confirmed' AND confirmed_at IS NOT NULL)
483 erp.payment_apply currency = 'KRW'
485 erp.payment_apply amount > 0
486 erp.payment_apply length(btrim(apply_key)) > 0
496 erp.tax_invoice currency = 'KRW'
499 erp.tax_invoice (status = 'pending' AND approval_no IS NULL AND issued_on IS NULL) OR (status = 'issued' AND approval_no IS NOT NULL AND length(btrim(approval_no)) > 0 AND issued_on IS NOT NULL)
505 erp.account (account_code = 'AR' AND account_name = '외상매출금') OR (account_code = 'PRODUCT_SALES' AND account_name = '제품매출') OR (account_code = 'VAT_PAYABLE' AND account_name = '부가세예수금') OR (account_code = 'BANK' AND account_name = '보통예금') OR (account_code = 'RAW_MATERIAL' AND account_name = '원재료') OR (account_code = 'VAT_RECEIVABLE' AND account_name = '부가세대급금') OR (account_code = 'AP' AND account_name = '외상매입금')
510 erp.posting_rule (transaction_kind = 'SALE' AND line_no = 1 AND entry_side = 'DEBIT' AND account_code = 'AR' AND amount_basis = 'TOTAL') OR (transaction_kind = 'SALE' AND line_no = 2 AND entry_side = 'CREDIT' AND account_code = 'PRODUCT_SALES' AND amount_basis = 'SUPPLY') OR (transaction_kind = 'SALE' AND line_no = 3 AND entry_side = 'CREDIT' AND account_code = 'VAT_PAYABLE' AND amount_basis = 'TAX') OR (transaction_kind = 'RECEIPT' AND line_no = 1 AND entry_side = 'DEBIT' AND account_code = 'BANK' AND amount_basis = 'APPLY') OR (transaction_kind = 'RECEIPT' AND line_no = 2 AND entry_side = 'CREDIT' AND account_code = 'AR' AND amount_basis = 'APPLY') OR (transaction_kind = 'PURCHASE' AND line_no = 1 AND entry_side = 'DEBIT' AND account_code = 'RAW_MATERIAL' AND amount_basis = 'SUPPLY') OR (transaction_kind = 'PURCHASE' AND line_no = 2 AND entry_side = 'DEBIT' AND account_code = 'VAT_RECEIVABLE' AND amount_basis = 'TAX') OR (transaction_kind = 'PURCHASE' AND line_no = 3 AND entry_side = 'CREDIT' AND account_code = 'AP' AND amount_basis = 'TOTAL') OR (transaction_kind = 'PAYMENT' AND line_no = 1 AND entry_side = 'DEBIT' AND account_code = 'AP' AND amount_basis = 'APPLY') OR (transaction_kind = 'PAYMENT' AND line_no = 2 AND entry_side = 'CREDIT' AND account_code = 'BANK' AND amount_basis = 'APPLY')
512 erp.purchase_invoice length(btrim(invoice_no)) > 0
513 erp.receipt length(btrim(receipt_no)) > 0
514 erp.payment length(btrim(payment_no)) > 0
515 erp.purchase_invoice_line length(btrim(unit)) > 0
517 erp.item tax_category IN ('TAXABLE','ZERO','EXEMPT')
521 erp.partner payment_term_days >= 0
"""


def expand(columns: str) -> str:
    return columns.replace("S,", "workspace_id,generation_id,")


def rows(block: str) -> list[str]:
    return block.strip().splitlines()


def upgrade() -> None:
    TABLES.clear()
    for schema in ("core", "mes", "erp", "fems"):
        op.execute(f"CREATE SCHEMA {schema}")
    create_tables()
    # 순환 참조(workspace↔generation)를 위해 테이블·키를 모두 만든 뒤 FK를 추가한다.
    for name in TABLES:
        op.execute(f"ALTER TABLE {name} ADD PRIMARY KEY (id)")
        if not name.startswith("core.") or name == "core.request_receipt":
            op.execute(
                f"ALTER TABLE {name} ADD CONSTRAINT {name.split('.')[1]}_scope_uk UNIQUE (workspace_id,generation_id,id)"
            )
    for row in rows(KEYS):
        number, name, columns = row.split()
        op.execute(
            f"ALTER TABLE {name} ADD CONSTRAINT c{number}_uk UNIQUE ({expand(columns)})"
        )
    for row in rows(CHECKS):
        number, name, expression = row.split(" ", 2)
        # 원문을 수정하지 않는다. 실패 시 C 번호·원문을 오류에 함께 남긴다.
        try:
            op.execute(
                f"ALTER TABLE {name} ADD CONSTRAINT c{number}_check CHECK ({expression})"
            )
        except Exception as exc:
            raise RuntimeError(f"C{number} {name}: {expression}\n{exc}") from exc
    for row in rows(INDEXES):
        number, name, columns = row.split()
        op.execute(f"CREATE INDEX c{number}_idx ON {name} ({expand(columns)})")
    for row in rows(PARTIALS):
        definition, predicate = row.split(" | ", 1)
        number, name, columns = definition.split()
        op.execute(
            f"CREATE UNIQUE INDEX c{number}_uidx ON {name} ({expand(columns)}) WHERE {predicate}"
        )
    for name in TABLES:
        if not name.startswith("core.") or name == "core.request_receipt":
            op.execute(
                f"ALTER TABLE {name} ADD CONSTRAINT generation_anchor FOREIGN KEY (workspace_id,generation_id) REFERENCES core.data_generation(workspace_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT"
            )
    for row in rows(FKS):
        number, name, columns, target, target_columns = row.split()
        op.execute(
            f"ALTER TABLE {name} ADD CONSTRAINT r{number}_fk FOREIGN KEY ({expand(columns)}) REFERENCES {target} ({expand(target_columns)}) ON DELETE RESTRICT ON UPDATE RESTRICT"
        )


OWNED_TABLES = [
    "core.app_user",
    "core.auth_session",
    "core.role",
    "core.user_role",
    "core.workspace",
    "core.data_generation",
    "core.workspace_module",
    "core.job_run",
    "core.audit_event",
    "core.request_receipt",
    "mes.site",
    "mes.location",
    "mes.equipment",
    "mes.item",
    "mes.item_unit_conversion",
    "mes.process",
    "mes.process_equipment",
    "mes.route_version",
    "mes.route_step",
    "mes.work_order",
    "mes.lot",
    "mes.operation_execution",
    "mes.operation_result",
    "mes.production_plan",
    "mes.production_plan_line",
    "mes.packing_unit",
    "mes.packing_member",
    "mes.finished_goods_receipt",
    "mes.bom_version",
    "mes.bom_line",
    "mes.material_issue",
    "fems.site",
    "fems.location",
    "fems.equipment",
    "fems.meter",
    "fems.energy_reading",
    "fems.energy_allocation",
    "fems.energy_source",
    "fems.meter_channel",
    "fems.energy_factor",
    "fems.tariff",
    "fems.energy_target",
    "fems.energy_baseline",
    "fems.production_record",
    "erp.item",
    "erp.item_unit_conversion",
    "erp.partner",
    "erp.sales_plan",
    "erp.sales_plan_line",
    "erp.sales_order",
    "erp.sales_order_line",
    "erp.shipment_order",
    "erp.shipment_order_line",
    "erp.shipment",
    "erp.shipment_line",
    "erp.sales_record",
    "erp.quotation",
    "erp.quotation_line",
    "erp.quotation_status_history",
    "erp.partner_item_price",
    "erp.purchase_invoice",
    "erp.purchase_invoice_line",
    "erp.receivable",
    "erp.payable",
    "erp.receipt",
    "erp.receipt_apply",
    "erp.payment",
    "erp.payment_apply",
    "erp.tax_invoice",
    "erp.account",
    "erp.posting_rule",
]


def downgrade() -> None:
    # 이 리비전 소유 FK와 테이블만 제거한다. 다른 객체가 있으면 CASCADE 없이 중단한다.
    for row in rows(FKS):
        number, name, *_ = row.split()
        op.execute(f"ALTER TABLE {name} DROP CONSTRAINT r{number}_fk")
    for name in OWNED_TABLES:
        if not name.startswith("core.") or name == "core.request_receipt":
            op.execute(f"ALTER TABLE {name} DROP CONSTRAINT generation_anchor")
    for name in reversed(OWNED_TABLES):
        op.execute(f"DROP TABLE {name}")
    for schema in ("mes", "erp", "fems", "core"):
        op.execute(f"DROP SCHEMA {schema}")

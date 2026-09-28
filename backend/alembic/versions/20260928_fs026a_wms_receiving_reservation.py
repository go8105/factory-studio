"""FS-026a WMS receiving/reservation additive schema, frozen v0.13.0.

SERVICE policies are metadata only until FS-026 API implementation.
Downgrade refuses data-bearing FS-026 state instead of deleting business history.
"""

from alembic import op

revision = "fs026a_wms_receiving_reservation"
down_revision = "fs025b_bems_module"
branch_labels = None
depends_on = None

UPGRADE_SQL = [
    "ALTER TABLE wms.storage_location ADD COLUMN location_type varchar(16) NOT NULL DEFAULT 'NORMAL'",
    "ALTER TABLE wms.stock_document DROP CONSTRAINT c620_check",
    "ALTER TABLE wms.stock_document ADD CONSTRAINT c620_check CHECK (document_type IN ('OPENING', 'MES_RECEIPT', 'MES_ISSUE', 'ERP_SHIPMENT', 'ERP_PURCHASE', 'WMS_INSPECTION', 'ADJUSTMENT', 'TRANSFER', 'REVERSAL'))",
    "ALTER TABLE wms.stock_document DROP CONSTRAINT c624_check",
    "ALTER TABLE wms.stock_document ADD CONSTRAINT c624_check CHECK ((document_type IN ('MES_RECEIPT', 'MES_ISSUE', 'ERP_SHIPMENT', 'ERP_PURCHASE', 'WMS_INSPECTION', 'REVERSAL')) = (source_key IS NOT NULL))",
    "CREATE TABLE wms.inbound_notice (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, notice_no varchar(40) NOT NULL, business_key varchar(100) NOT NULL, warehouse_id bigint NOT NULL, status varchar(16) NOT NULL DEFAULT 'PLANNED', expected_on date NOT NULL, vehicle_no varchar(40), partner_ref varchar(100), version integer NOT NULL DEFAULT 1, arrived_at timestamptz, inspected_at timestamptz, cancelled_at timestamptz, stock_document_id bigint, reason varchar(300), updated_at timestamptz NOT NULL DEFAULT clock_timestamp(), created_at timestamptz NOT NULL DEFAULT clock_timestamp())",
    "CREATE TABLE wms.inbound_notice_line (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, notice_id bigint NOT NULL, line_no integer NOT NULL, item_id bigint NOT NULL, lot_no varchar(50), expected_qty numeric(18,3) NOT NULL, accepted_qty numeric(18,3), quarantined_qty numeric(18,3), shortage_qty numeric(18,3), normal_location_id bigint NOT NULL, quarantine_location_id bigint, reason varchar(300), created_at timestamptz NOT NULL DEFAULT clock_timestamp())",
    "CREATE TABLE wms.source_claim (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, source_key varchar(100) NOT NULL, notice_id bigint NOT NULL, status varchar(16) NOT NULL DEFAULT 'CLAIMED', source_snapshot jsonb NOT NULL, source_digest varchar(64) NOT NULL, closed_at timestamptz, release_reason varchar(300), created_at timestamptz NOT NULL DEFAULT clock_timestamp())",
    "CREATE TABLE wms.stock_reservation (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, reservation_no varchar(40) NOT NULL, business_key varchar(100) NOT NULL, status varchar(16) NOT NULL DEFAULT 'ACTIVE', shipment_order_ref varchar(40), version integer NOT NULL DEFAULT 1, reason varchar(300), closed_at timestamptz, shipment_source_key varchar(100), stock_document_id bigint, created_at timestamptz NOT NULL DEFAULT clock_timestamp())",
    "CREATE TABLE wms.stock_reservation_line (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, reservation_id bigint NOT NULL, line_no integer NOT NULL, item_id bigint NOT NULL, location_id bigint NOT NULL, lot_no varchar(50), quantity numeric(18,3) NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp())",
    "ALTER TABLE wms.inbound_notice ADD CONSTRAINT c726_pk PRIMARY KEY (id)",
    "ALTER TABLE wms.inbound_notice ADD CONSTRAINT c727_uk UNIQUE (workspace_id, generation_id, id)",
    "ALTER TABLE wms.inbound_notice_line ADD CONSTRAINT c728_pk PRIMARY KEY (id)",
    "ALTER TABLE wms.inbound_notice_line ADD CONSTRAINT c729_uk UNIQUE (workspace_id, generation_id, id)",
    "ALTER TABLE wms.source_claim ADD CONSTRAINT c730_pk PRIMARY KEY (id)",
    "ALTER TABLE wms.source_claim ADD CONSTRAINT c731_uk UNIQUE (workspace_id, generation_id, id)",
    "ALTER TABLE wms.stock_reservation ADD CONSTRAINT c732_pk PRIMARY KEY (id)",
    "ALTER TABLE wms.stock_reservation ADD CONSTRAINT c733_uk UNIQUE (workspace_id, generation_id, id)",
    "ALTER TABLE wms.stock_reservation_line ADD CONSTRAINT c734_pk PRIMARY KEY (id)",
    "ALTER TABLE wms.stock_reservation_line ADD CONSTRAINT c735_uk UNIQUE (workspace_id, generation_id, id)",
    "ALTER TABLE wms.inbound_notice ADD CONSTRAINT c736_uk UNIQUE (workspace_id, generation_id, notice_no)",
    "ALTER TABLE wms.inbound_notice ADD CONSTRAINT c737_uk UNIQUE (workspace_id, generation_id, business_key)",
    "ALTER TABLE wms.inbound_notice ADD CONSTRAINT c738_check CHECK (length(btrim(notice_no)) > 0 AND length(btrim(business_key)) > 0)",
    "ALTER TABLE wms.inbound_notice ADD CONSTRAINT c739_check CHECK (version > 0)",
    "ALTER TABLE wms.stock_reservation ADD CONSTRAINT c740_uk UNIQUE (workspace_id, generation_id, reservation_no)",
    "ALTER TABLE wms.stock_reservation ADD CONSTRAINT c741_uk UNIQUE (workspace_id, generation_id, business_key)",
    "ALTER TABLE wms.stock_reservation ADD CONSTRAINT c742_check CHECK (length(btrim(reservation_no)) > 0 AND length(btrim(business_key)) > 0)",
    "ALTER TABLE wms.stock_reservation ADD CONSTRAINT c743_check CHECK (version > 0)",
    "ALTER TABLE wms.inbound_notice ADD CONSTRAINT c744_check CHECK (status IN ('PLANNED', 'ARRIVED', 'INSPECTED', 'CANCELLED'))",
    "ALTER TABLE wms.source_claim ADD CONSTRAINT c745_check CHECK (status IN ('CLAIMED', 'COMPLETED', 'RELEASED'))",
    "ALTER TABLE wms.stock_reservation ADD CONSTRAINT c746_check CHECK (status IN ('ACTIVE', 'RELEASED', 'CONSUMED'))",
    "ALTER TABLE wms.inbound_notice ADD CONSTRAINT c747_check CHECK ((status = 'INSPECTED') = (inspected_at IS NOT NULL))",
    "ALTER TABLE wms.inbound_notice ADD CONSTRAINT c748_check CHECK ((status = 'CANCELLED') = (cancelled_at IS NOT NULL))",
    "ALTER TABLE wms.inbound_notice ADD CONSTRAINT c749_check CHECK ((status NOT IN ('ARRIVED','INSPECTED') OR arrived_at IS NOT NULL) AND (status <> 'PLANNED' OR arrived_at IS NULL))",
    "ALTER TABLE wms.inbound_notice ADD CONSTRAINT c750_check CHECK (stock_document_id IS NULL OR status = 'INSPECTED')",
    "ALTER TABLE wms.inbound_notice ADD CONSTRAINT c751_check CHECK (status <> 'CANCELLED' OR (reason IS NOT NULL AND length(btrim(reason)) > 0))",
    "CREATE UNIQUE INDEX c752_uidx ON wms.inbound_notice (workspace_id, generation_id, stock_document_id) WHERE stock_document_id IS NOT NULL",
    "ALTER TABLE wms.inbound_notice_line ADD CONSTRAINT c753_uk UNIQUE (workspace_id, generation_id, notice_id, line_no)",
    "ALTER TABLE wms.inbound_notice_line ADD CONSTRAINT c754_check CHECK (line_no > 0)",
    "ALTER TABLE wms.inbound_notice_line ADD CONSTRAINT c755_check CHECK (lot_no IS NULL OR length(btrim(lot_no)) > 0)",
    "CREATE UNIQUE INDEX c756_uidx ON wms.inbound_notice_line (workspace_id, generation_id, notice_id, item_id) WHERE lot_no IS NULL",
    "CREATE UNIQUE INDEX c757_uidx ON wms.inbound_notice_line (workspace_id, generation_id, notice_id, item_id, lot_no) WHERE lot_no IS NOT NULL",
    "ALTER TABLE wms.stock_reservation_line ADD CONSTRAINT c758_uk UNIQUE (workspace_id, generation_id, reservation_id, line_no)",
    "ALTER TABLE wms.stock_reservation_line ADD CONSTRAINT c759_check CHECK (line_no > 0)",
    "ALTER TABLE wms.stock_reservation_line ADD CONSTRAINT c760_check CHECK (lot_no IS NULL OR length(btrim(lot_no)) > 0)",
    "CREATE UNIQUE INDEX c761_uidx ON wms.stock_reservation_line (workspace_id, generation_id, reservation_id, item_id, location_id) WHERE lot_no IS NULL",
    "CREATE UNIQUE INDEX c762_uidx ON wms.stock_reservation_line (workspace_id, generation_id, reservation_id, item_id, location_id, lot_no) WHERE lot_no IS NOT NULL",
    "ALTER TABLE wms.inbound_notice_line ADD CONSTRAINT c763_check CHECK (expected_qty > 0)",
    "ALTER TABLE wms.inbound_notice_line ADD CONSTRAINT c764_check CHECK ((accepted_qty IS NULL AND quarantined_qty IS NULL AND shortage_qty IS NULL) OR (accepted_qty IS NOT NULL AND accepted_qty >= 0 AND quarantined_qty IS NOT NULL AND quarantined_qty >= 0 AND shortage_qty IS NOT NULL AND shortage_qty >= 0 AND accepted_qty + quarantined_qty + shortage_qty = expected_qty))",
    "ALTER TABLE wms.inbound_notice_line ADD CONSTRAINT c765_check CHECK (quarantined_qty IS NULL OR quarantined_qty = 0 OR quarantine_location_id IS NOT NULL)",
    "ALTER TABLE wms.inbound_notice_line ADD CONSTRAINT c766_check CHECK (NOT (coalesce(quarantined_qty,0) > 0 OR coalesce(shortage_qty,0) > 0) OR (reason IS NOT NULL AND length(btrim(reason)) > 0))",
    "ALTER TABLE wms.stock_reservation_line ADD CONSTRAINT c767_check CHECK (quantity > 0)",
    "ALTER TABLE wms.source_claim ADD CONSTRAINT c768_check CHECK (source_key ~ '^ERP:PURCHASE:.+$')",
    "ALTER TABLE wms.source_claim ADD CONSTRAINT c769_check CHECK (jsonb_typeof(source_snapshot) = 'object')",
    "ALTER TABLE wms.source_claim ADD CONSTRAINT c770_check CHECK (source_digest ~ '^[0-9a-f]{64}$')",
    "ALTER TABLE wms.source_claim ADD CONSTRAINT c771_check CHECK ((status = 'CLAIMED') = (closed_at IS NULL))",
    "ALTER TABLE wms.source_claim ADD CONSTRAINT c772_check CHECK (status <> 'RELEASED' OR (release_reason IS NOT NULL AND length(btrim(release_reason)) > 0))",
    "CREATE UNIQUE INDEX c773_uidx ON wms.source_claim (workspace_id, generation_id, source_key) WHERE status <> 'RELEASED'",
    "CREATE UNIQUE INDEX c774_uidx ON wms.source_claim (workspace_id, generation_id, notice_id) WHERE status <> 'RELEASED'",
    "ALTER TABLE wms.stock_reservation ADD CONSTRAINT c775_check CHECK ((status = 'ACTIVE') = (closed_at IS NULL))",
    "ALTER TABLE wms.stock_reservation ADD CONSTRAINT c776_check CHECK ((status = 'CONSUMED' AND shipment_source_key IS NOT NULL AND stock_document_id IS NOT NULL) OR (status <> 'CONSUMED' AND shipment_source_key IS NULL AND stock_document_id IS NULL))",
    "ALTER TABLE wms.stock_reservation ADD CONSTRAINT c777_check CHECK (shipment_source_key IS NULL OR shipment_source_key ~ '^ERP:SHIPMENT:.+$')",
    "ALTER TABLE wms.stock_reservation ADD CONSTRAINT c778_check CHECK (status <> 'RELEASED' OR (reason IS NOT NULL AND length(btrim(reason)) > 0))",
    "CREATE UNIQUE INDEX c779_uidx ON wms.stock_reservation (workspace_id, generation_id, shipment_source_key) WHERE shipment_source_key IS NOT NULL",
    "CREATE UNIQUE INDEX c780_uidx ON wms.stock_reservation (workspace_id, generation_id, stock_document_id) WHERE stock_document_id IS NOT NULL",
    "ALTER TABLE wms.storage_location ADD CONSTRAINT c781_check CHECK (location_type IN ('NORMAL','QUARANTINE'))",
    "ALTER TABLE wms.storage_location ADD CONSTRAINT c782_check CHECK (NOT is_default OR location_type = 'NORMAL')",
    "CREATE INDEX c790_idx ON wms.inbound_notice (workspace_id, generation_id, warehouse_id)",
    "CREATE INDEX c791_idx ON wms.inbound_notice (workspace_id, generation_id, stock_document_id)",
    "CREATE INDEX c792_idx ON wms.inbound_notice_line (workspace_id, generation_id, notice_id)",
    "CREATE INDEX c793_idx ON wms.inbound_notice_line (workspace_id, generation_id, item_id)",
    "CREATE INDEX c794_idx ON wms.inbound_notice_line (workspace_id, generation_id, normal_location_id)",
    "CREATE INDEX c795_idx ON wms.inbound_notice_line (workspace_id, generation_id, quarantine_location_id)",
    "CREATE INDEX c796_idx ON wms.source_claim (workspace_id, generation_id, notice_id)",
    "CREATE INDEX c797_idx ON wms.stock_reservation (workspace_id, generation_id, stock_document_id)",
    "CREATE INDEX c798_idx ON wms.stock_reservation_line (workspace_id, generation_id, reservation_id)",
    "CREATE INDEX c799_idx ON wms.stock_reservation_line (workspace_id, generation_id, item_id)",
    "CREATE INDEX c800_idx ON wms.stock_reservation_line (workspace_id, generation_id, location_id)",
    "CREATE INDEX c801_idx ON wms.inbound_notice (workspace_id, generation_id, status, expected_on)",
    "CREATE INDEX c802_idx ON wms.source_claim (workspace_id, generation_id, source_key)",
    "CREATE INDEX c803_idx ON wms.stock_reservation (workspace_id, generation_id, status)",
    "CREATE INDEX c804_idx ON wms.stock_reservation_line (workspace_id, generation_id, item_id, location_id, lot_no)",
    "ALTER TABLE wms.inbound_notice ADD CONSTRAINT generation_anchor FOREIGN KEY (workspace_id, generation_id) REFERENCES core.data_generation (workspace_id, id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE wms.inbound_notice_line ADD CONSTRAINT generation_anchor FOREIGN KEY (workspace_id, generation_id) REFERENCES core.data_generation (workspace_id, id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE wms.source_claim ADD CONSTRAINT generation_anchor FOREIGN KEY (workspace_id, generation_id) REFERENCES core.data_generation (workspace_id, id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE wms.stock_reservation ADD CONSTRAINT generation_anchor FOREIGN KEY (workspace_id, generation_id) REFERENCES core.data_generation (workspace_id, id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE wms.stock_reservation_line ADD CONSTRAINT generation_anchor FOREIGN KEY (workspace_id, generation_id) REFERENCES core.data_generation (workspace_id, id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE wms.inbound_notice ADD CONSTRAINT r214_fk FOREIGN KEY (workspace_id, generation_id, warehouse_id) REFERENCES wms.warehouse (workspace_id, generation_id, id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE wms.inbound_notice ADD CONSTRAINT r215_fk FOREIGN KEY (workspace_id, generation_id, stock_document_id) REFERENCES wms.stock_document (workspace_id, generation_id, id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE wms.inbound_notice_line ADD CONSTRAINT r216_fk FOREIGN KEY (workspace_id, generation_id, notice_id) REFERENCES wms.inbound_notice (workspace_id, generation_id, id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE wms.inbound_notice_line ADD CONSTRAINT r217_fk FOREIGN KEY (workspace_id, generation_id, item_id) REFERENCES wms.item (workspace_id, generation_id, id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE wms.inbound_notice_line ADD CONSTRAINT r218_fk FOREIGN KEY (workspace_id, generation_id, normal_location_id) REFERENCES wms.storage_location (workspace_id, generation_id, id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE wms.inbound_notice_line ADD CONSTRAINT r219_fk FOREIGN KEY (workspace_id, generation_id, quarantine_location_id) REFERENCES wms.storage_location (workspace_id, generation_id, id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE wms.source_claim ADD CONSTRAINT r220_fk FOREIGN KEY (workspace_id, generation_id, notice_id) REFERENCES wms.inbound_notice (workspace_id, generation_id, id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE wms.stock_reservation ADD CONSTRAINT r221_fk FOREIGN KEY (workspace_id, generation_id, stock_document_id) REFERENCES wms.stock_document (workspace_id, generation_id, id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE wms.stock_reservation_line ADD CONSTRAINT r222_fk FOREIGN KEY (workspace_id, generation_id, reservation_id) REFERENCES wms.stock_reservation (workspace_id, generation_id, id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE wms.stock_reservation_line ADD CONSTRAINT r223_fk FOREIGN KEY (workspace_id, generation_id, item_id) REFERENCES wms.item (workspace_id, generation_id, id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE wms.stock_reservation_line ADD CONSTRAINT r224_fk FOREIGN KEY (workspace_id, generation_id, location_id) REFERENCES wms.storage_location (workspace_id, generation_id, id) ON DELETE RESTRICT ON UPDATE RESTRICT",
]

DOWNGRADE_SQL = [
    "DO $$ BEGIN IF EXISTS (SELECT 1 FROM wms.inbound_notice) OR EXISTS (SELECT 1 FROM wms.inbound_notice_line) OR EXISTS (SELECT 1 FROM wms.source_claim) OR EXISTS (SELECT 1 FROM wms.stock_reservation) OR EXISTS (SELECT 1 FROM wms.stock_reservation_line) OR EXISTS (SELECT 1 FROM wms.stock_document WHERE document_type='WMS_INSPECTION') OR EXISTS (SELECT 1 FROM wms.storage_location WHERE location_type<>'NORMAL') THEN RAISE EXCEPTION 'FS-026 downgrade refused: receiving/reservation/quarantine data exists'; END IF; END $$",
    "DROP TABLE wms.stock_reservation_line",
    "DROP TABLE wms.stock_reservation",
    "DROP TABLE wms.source_claim",
    "DROP TABLE wms.inbound_notice_line",
    "DROP TABLE wms.inbound_notice",
    "ALTER TABLE wms.storage_location DROP CONSTRAINT c782_check",
    "ALTER TABLE wms.storage_location DROP CONSTRAINT c781_check",
    "ALTER TABLE wms.stock_document DROP CONSTRAINT c620_check",
    "ALTER TABLE wms.stock_document ADD CONSTRAINT c620_check CHECK (document_type IN ('OPENING', 'MES_RECEIPT', 'MES_ISSUE', 'ERP_SHIPMENT', 'ERP_PURCHASE', 'ADJUSTMENT', 'TRANSFER', 'REVERSAL'))",
    "ALTER TABLE wms.stock_document DROP CONSTRAINT c624_check",
    "ALTER TABLE wms.stock_document ADD CONSTRAINT c624_check CHECK ((document_type IN ('MES_RECEIPT', 'MES_ISSUE', 'ERP_SHIPMENT', 'ERP_PURCHASE', 'REVERSAL')) = (source_key IS NOT NULL))",
    "ALTER TABLE wms.storage_location DROP COLUMN location_type",
]


def upgrade() -> None:
    for statement in UPGRADE_SQL:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE_SQL:
        op.execute(statement)

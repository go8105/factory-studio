"""GW-COMPANY-05: 이미 적용된 WMS/GW 분기를 보존해 통합한다."""

from alembic import op

revision = "gw_wms_merge"
down_revision = ("w2b1_wms", "gw_company_identity")
branch_labels = None
depends_on = None

# (table, GW branch name, integrated name, standalone index)
RENAMES = [
    ("gw.collaboration_settings", "c1441_pk", "c1515_pk", False),
    ("gw.collaboration_settings", "c1442_uk", "c1516_uk", False),
    ("gw.collaboration_settings", "c1443_idx", "c1517_idx", True),
    ("gw.person_identity_binding", "c1444_pk", "c1518_pk", False),
    ("gw.person_identity_binding", "c1445_uk", "c1519_uk", False),
    ("gw.person_identity_binding", "c1446_idx", "c1520_idx", True),
    ("gw.person_identity_binding", "c1447_check", "c1521_check", False),
    ("gw.role_grant", "c1448_pk", "c1522_pk", False),
    ("gw.role_grant", "c1449_uk", "c1523_uk", False),
    ("gw.role_grant", "c1450_idx", "c1524_idx", True),
    ("gw.role_grant", "c1451_check", "c1525_check", False),
    ("gw.role_grant", "c1452_check", "c1526_check", False),
    ("gw.document_reader", "c1453_pk", "c1527_pk", False),
    ("gw.document_reader", "c1454_uk", "c1528_uk", False),
    ("gw.document_reader", "c1455_idx", "c1529_idx", True),
    ("gw.document_reader", "c1456_check", "c1530_check", False),
    ("gw.document_reader", "c1457_check", "c1531_check", False),
    ("gw.step_assignment", "c1458_pk", "c1532_pk", False),
    ("gw.step_assignment", "c1459_uk", "c1533_uk", False),
    ("gw.step_assignment", "c1460_idx", "c1534_idx", True),
    ("gw.step_assignment", "c1461_check", "c1535_check", False),
    ("gw.collaboration_settings", "c1462_uk", "c1536_uk", False),
    ("gw.collaboration_settings", "c1463_check", "c1537_check", False),
    ("gw.person_identity_binding", "c1464_uidx", "c1538_uidx", True),
    ("gw.person_identity_binding", "c1465_uidx", "c1539_uidx", True),
    ("gw.person_identity_binding", "c1466_check", "c1540_check", False),
    ("gw.person_identity_binding", "c1467_check", "c1541_check", False),
    ("gw.role_grant", "c1468_uk", "c1542_uk", False),
    ("gw.role_grant", "c1469_check", "c1543_check", False),
    ("gw.document_reader", "c1470_uk", "c1544_uk", False),
    ("gw.document_reader", "c1471_idx", "c1545_idx", True),
    ("gw.approval_step", "c1472_uk", "c1546_uk", False),
    ("gw.step_assignment", "c1473_uk", "c1547_uk", False),
    ("gw.step_assignment", "c1474_check", "c1548_check", False),
    ("gw.collaboration_settings", "r471_fk", "r507_fk", False),
    ("gw.collaboration_settings", "r472_fk", "r508_fk", False),
    ("gw.person_identity_binding", "r473_fk", "r509_fk", False),
    ("gw.person_identity_binding", "r474_fk", "r510_fk", False),
    ("gw.person_identity_binding", "r475_fk", "r511_fk", False),
    ("gw.role_grant", "r476_fk", "r512_fk", False),
    ("gw.role_grant", "r477_fk", "r513_fk", False),
    ("gw.role_grant", "r478_fk", "r514_fk", False),
    ("gw.document_reader", "r479_fk", "r515_fk", False),
    ("gw.document_reader", "r480_fk", "r516_fk", False),
    ("gw.document_reader", "r481_fk", "r517_fk", False),
    ("gw.document_reader", "r482_fk", "r518_fk", False),
    ("gw.step_assignment", "r483_fk", "r519_fk", False),
    ("gw.step_assignment", "r484_fk", "r520_fk", False),
    ("gw.step_assignment", "r485_fk", "r521_fk", False),
    ("gw.step_assignment", "r486_fk", "r522_fk", False),
    ("gw.step_assignment", "r487_fk", "r523_fk", False),
]


def rename(reverse=False):
    for table, before, after, index in reversed(RENAMES) if reverse else RENAMES:
        if reverse:
            before, after = after, before
        if index:
            schema = table.split(".")[0]
            op.execute(f"ALTER INDEX {schema}.{before} RENAME TO {after}")
        else:
            op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {before} TO {after}")


def upgrade():
    rename()


def downgrade():
    # Name-only rollback preserves every business/security row.
    # The parent GW revision separately forbids removal of populated security tables.
    rename(reverse=True)

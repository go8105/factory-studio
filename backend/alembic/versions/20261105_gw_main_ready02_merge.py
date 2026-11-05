"""GW/main integration: validate every object, then rename without rewriting rows.

Frozen from GW 4c898ac / main 783a2c1; main metadata order + GW additions.
No runtime metadata-file lookup and no parent migration or security-history deletion.
"""

from __future__ import annotations

import re
from uuid import uuid4

from alembic import op
from sqlalchemy import text

revision = "gw_main_ready02_merge"
down_revision = ("gw_readiness", "fems1")
branch_labels = None
depends_on = None

RENAMES = [
    {
        "table": "core.mfa_factor",
        "from": "c1549_pk",
        "to": "c1772_pk",
        "kind": "PK",
        "definition": {
            "table": "core.mfa_factor",
            "kind": "PK",
            "columns": ["id"],
            "expression": "",
        },
    },
    {
        "table": "core.authentication_challenge",
        "from": "c1550_pk",
        "to": "c1773_pk",
        "kind": "PK",
        "definition": {
            "table": "core.authentication_challenge",
            "kind": "PK",
            "columns": ["id"],
            "expression": "",
        },
    },
    {
        "table": "core.recovery_code",
        "from": "c1551_pk",
        "to": "c1774_pk",
        "kind": "PK",
        "definition": {
            "table": "core.recovery_code",
            "kind": "PK",
            "columns": ["id"],
            "expression": "",
        },
    },
    {
        "table": "core.sso_identity",
        "from": "c1552_pk",
        "to": "c1775_pk",
        "kind": "PK",
        "definition": {
            "table": "core.sso_identity",
            "kind": "PK",
            "columns": ["id"],
            "expression": "",
        },
    },
    {
        "table": "core.authentication_throttle",
        "from": "c1553_pk",
        "to": "c1776_pk",
        "kind": "PK",
        "definition": {
            "table": "core.authentication_throttle",
            "kind": "PK",
            "columns": ["id"],
            "expression": "",
        },
    },
    {
        "table": "gw.operating_settings",
        "from": "c1554_pk",
        "to": "c1777_pk",
        "kind": "PK",
        "definition": {
            "table": "gw.operating_settings",
            "kind": "PK",
            "columns": ["id"],
            "expression": "",
        },
    },
    {
        "table": "gw.operating_settings",
        "from": "c1555_uk",
        "to": "c1778_uk",
        "kind": "UK",
        "definition": {
            "table": "gw.operating_settings",
            "kind": "UK",
            "columns": ["workspace_id", "generation_id", "id"],
            "expression": "",
        },
    },
    {
        "table": "gw.operating_settings",
        "from": "c1556_idx",
        "to": "c1779_idx",
        "kind": "INDEX",
        "definition": {
            "table": "gw.operating_settings",
            "kind": "INDEX",
            "columns": ["workspace_id", "generation_id"],
            "expression": "",
        },
    },
    {
        "table": "gw.operating_policy_revision",
        "from": "c1557_pk",
        "to": "c1780_pk",
        "kind": "PK",
        "definition": {
            "table": "gw.operating_policy_revision",
            "kind": "PK",
            "columns": ["id"],
            "expression": "",
        },
    },
    {
        "table": "gw.operating_policy_revision",
        "from": "c1558_uk",
        "to": "c1781_uk",
        "kind": "UK",
        "definition": {
            "table": "gw.operating_policy_revision",
            "kind": "UK",
            "columns": ["workspace_id", "generation_id", "id"],
            "expression": "",
        },
    },
    {
        "table": "gw.operating_policy_revision",
        "from": "c1559_idx",
        "to": "c1782_idx",
        "kind": "INDEX",
        "definition": {
            "table": "gw.operating_policy_revision",
            "kind": "INDEX",
            "columns": ["workspace_id", "generation_id"],
            "expression": "",
        },
    },
    {
        "table": "gw.operating_evidence",
        "from": "c1560_pk",
        "to": "c1783_pk",
        "kind": "PK",
        "definition": {
            "table": "gw.operating_evidence",
            "kind": "PK",
            "columns": ["id"],
            "expression": "",
        },
    },
    {
        "table": "gw.operating_evidence",
        "from": "c1561_uk",
        "to": "c1784_uk",
        "kind": "UK",
        "definition": {
            "table": "gw.operating_evidence",
            "kind": "UK",
            "columns": ["workspace_id", "generation_id", "id"],
            "expression": "",
        },
    },
    {
        "table": "gw.operating_evidence",
        "from": "c1562_idx",
        "to": "c1785_idx",
        "kind": "INDEX",
        "definition": {
            "table": "gw.operating_evidence",
            "kind": "INDEX",
            "columns": ["workspace_id", "generation_id"],
            "expression": "",
        },
    },
    {
        "table": "gw.retention_review",
        "from": "c1563_pk",
        "to": "c1786_pk",
        "kind": "PK",
        "definition": {
            "table": "gw.retention_review",
            "kind": "PK",
            "columns": ["id"],
            "expression": "",
        },
    },
    {
        "table": "gw.retention_review",
        "from": "c1564_uk",
        "to": "c1787_uk",
        "kind": "UK",
        "definition": {
            "table": "gw.retention_review",
            "kind": "UK",
            "columns": ["workspace_id", "generation_id", "id"],
            "expression": "",
        },
    },
    {
        "table": "gw.retention_review",
        "from": "c1565_idx",
        "to": "c1788_idx",
        "kind": "INDEX",
        "definition": {
            "table": "gw.retention_review",
            "kind": "INDEX",
            "columns": ["workspace_id", "generation_id"],
            "expression": "",
        },
    },
    {
        "table": "core.app_user",
        "from": "c1566_check",
        "to": "c1789_check",
        "kind": "CHECK",
        "definition": {
            "table": "core.app_user",
            "kind": "CHECK",
            "columns": ["security_version"],
            "expression": "security_version>0",
        },
    },
    {
        "table": "core.auth_session",
        "from": "c1567_uk",
        "to": "c1790_uk",
        "kind": "UK",
        "definition": {
            "table": "core.auth_session",
            "kind": "UK",
            "columns": ["user_id", "id"],
            "expression": "",
        },
    },
    {
        "table": "core.auth_session",
        "from": "c1568_check",
        "to": "c1791_check",
        "kind": "CHECK",
        "definition": {
            "table": "core.auth_session",
            "kind": "CHECK",
            "columns": ["security_version"],
            "expression": "security_version>0",
        },
    },
    {
        "table": "core.auth_session",
        "from": "c1569_check",
        "to": "c1792_check",
        "kind": "CHECK",
        "definition": {
            "table": "core.auth_session",
            "kind": "CHECK",
            "columns": ["assurance"],
            "expression": "assurance IN ('PASSWORD','MFA','RECOVERY_LIMITED','OIDC')",
        },
    },
    {
        "table": "core.auth_session",
        "from": "c1570_check",
        "to": "c1793_check",
        "kind": "CHECK",
        "definition": {
            "table": "core.auth_session",
            "kind": "CHECK",
            "columns": ["auth_method"],
            "expression": "auth_method IN ('PASSWORD','TOTP','RECOVERY','OIDC')",
        },
    },
    {
        "table": "core.mfa_factor",
        "from": "c1571_uk",
        "to": "c1794_uk",
        "kind": "UK",
        "definition": {
            "table": "core.mfa_factor",
            "kind": "UK",
            "columns": ["user_id", "id"],
            "expression": "",
        },
    },
    {
        "table": "core.mfa_factor",
        "from": "c1572_uidx",
        "to": "c1795_uidx",
        "kind": "UK_PARTIAL",
        "definition": {
            "table": "core.mfa_factor",
            "kind": "UK_PARTIAL",
            "columns": ["user_id", "kind"],
            "expression": "UNIQUE WHERE state='ACTIVE'",
        },
    },
    {
        "table": "core.mfa_factor",
        "from": "c1573_uidx",
        "to": "c1796_uidx",
        "kind": "UK_PARTIAL",
        "definition": {
            "table": "core.mfa_factor",
            "kind": "UK_PARTIAL",
            "columns": ["user_id", "kind"],
            "expression": "UNIQUE WHERE state='PENDING'",
        },
    },
    {
        "table": "core.mfa_factor",
        "from": "c1574_check",
        "to": "c1797_check",
        "kind": "CHECK",
        "definition": {
            "table": "core.mfa_factor",
            "kind": "CHECK",
            "columns": ["kind"],
            "expression": "kind='TOTP'",
        },
    },
    {
        "table": "core.mfa_factor",
        "from": "c1575_check",
        "to": "c1798_check",
        "kind": "CHECK",
        "definition": {
            "table": "core.mfa_factor",
            "kind": "CHECK",
            "columns": ["version"],
            "expression": "version>0",
        },
    },
    {
        "table": "core.mfa_factor",
        "from": "c1576_check",
        "to": "c1799_check",
        "kind": "CHECK",
        "definition": {
            "table": "core.mfa_factor",
            "kind": "CHECK",
            "columns": ["state", "pending_expires_at", "confirmed_at", "revoked_at"],
            "expression": "(state='PENDING' AND pending_expires_at IS NOT NULL AND revoked_at "
            "IS NULL) OR (state='ACTIVE' AND confirmed_at IS NOT NULL AND "
            "revoked_at IS NULL) OR (state='REVOKED' AND revoked_at IS NOT "
            "NULL)",
        },
    },
    {
        "table": "core.authentication_challenge",
        "from": "c1577_uk",
        "to": "c1800_uk",
        "kind": "UK",
        "definition": {
            "table": "core.authentication_challenge",
            "kind": "UK",
            "columns": ["token_hash"],
            "expression": "",
        },
    },
    {
        "table": "core.authentication_challenge",
        "from": "c1578_check",
        "to": "c1801_check",
        "kind": "CHECK",
        "definition": {
            "table": "core.authentication_challenge",
            "kind": "CHECK",
            "columns": ["state"],
            "expression": "state IN ('PENDING','CONSUMED','EXPIRED','LOCKED')",
        },
    },
    {
        "table": "core.authentication_challenge",
        "from": "c1579_check",
        "to": "c1802_check",
        "kind": "CHECK",
        "definition": {
            "table": "core.authentication_challenge",
            "kind": "CHECK",
            "columns": ["purpose"],
            "expression": "purpose IN "
            "('LOGIN_MFA','STEP_UP','ENROLL','OIDC_LOGIN','OIDC_LINK','RECOVERY')",
        },
    },
    {
        "table": "core.authentication_challenge",
        "from": "c1580_check",
        "to": "c1803_check",
        "kind": "CHECK",
        "definition": {
            "table": "core.authentication_challenge",
            "kind": "CHECK",
            "columns": ["attempt_count"],
            "expression": "attempt_count>=0",
        },
    },
    {
        "table": "core.authentication_challenge",
        "from": "c1581_check",
        "to": "c1804_check",
        "kind": "CHECK",
        "definition": {
            "table": "core.authentication_challenge",
            "kind": "CHECK",
            "columns": ["expires_at", "created_at"],
            "expression": "expires_at>created_at",
        },
    },
    {
        "table": "core.authentication_challenge",
        "from": "c1582_check",
        "to": "c1805_check",
        "kind": "CHECK",
        "definition": {
            "table": "core.authentication_challenge",
            "kind": "CHECK",
            "columns": ["state", "consumed_at"],
            "expression": "state<>'CONSUMED' OR consumed_at IS NOT NULL",
        },
    },
    {
        "table": "core.authentication_challenge",
        "from": "c1583_check",
        "to": "c1806_check",
        "kind": "CHECK",
        "definition": {
            "table": "core.authentication_challenge",
            "kind": "CHECK",
            "columns": ["purpose", "user_id", "session_id"],
            "expression": "(purpose='OIDC_LOGIN' OR user_id IS NOT NULL) AND (purpose NOT IN "
            "('STEP_UP','OIDC_LINK') OR session_id IS NOT NULL)",
        },
    },
    {
        "table": "core.authentication_challenge",
        "from": "c1584_check",
        "to": "c1807_check",
        "kind": "CHECK",
        "definition": {
            "table": "core.authentication_challenge",
            "kind": "CHECK",
            "columns": ["protected_payload", "encryption_key_id"],
            "expression": "(protected_payload IS NULL)=(encryption_key_id IS NULL)",
        },
    },
    {
        "table": "core.authentication_challenge",
        "from": "c1585_idx",
        "to": "c1808_idx",
        "kind": "INDEX",
        "definition": {
            "table": "core.authentication_challenge",
            "kind": "INDEX",
            "columns": ["expires_at"],
            "expression": "",
        },
    },
    {
        "table": "core.recovery_code",
        "from": "c1586_uk",
        "to": "c1809_uk",
        "kind": "UK",
        "definition": {
            "table": "core.recovery_code",
            "kind": "UK",
            "columns": ["user_id", "code_hash"],
            "expression": "",
        },
    },
    {
        "table": "core.recovery_code",
        "from": "c1587_check",
        "to": "c1810_check",
        "kind": "CHECK",
        "definition": {
            "table": "core.recovery_code",
            "kind": "CHECK",
            "columns": ["factor_version"],
            "expression": "factor_version>0",
        },
    },
    {
        "table": "core.sso_identity",
        "from": "c1588_uk",
        "to": "c1811_uk",
        "kind": "UK",
        "definition": {
            "table": "core.sso_identity",
            "kind": "UK",
            "columns": ["issuer", "subject"],
            "expression": "",
        },
    },
    {
        "table": "core.sso_identity",
        "from": "c1589_uidx",
        "to": "c1812_uidx",
        "kind": "UK_PARTIAL",
        "definition": {
            "table": "core.sso_identity",
            "kind": "UK_PARTIAL",
            "columns": ["user_id", "provider_key"],
            "expression": "UNIQUE WHERE state='ACTIVE'",
        },
    },
    {
        "table": "core.sso_identity",
        "from": "c1590_check",
        "to": "c1813_check",
        "kind": "CHECK",
        "definition": {
            "table": "core.sso_identity",
            "kind": "CHECK",
            "columns": ["state", "revoked_at"],
            "expression": "(state='ACTIVE' AND revoked_at IS NULL) OR (state='REVOKED' AND "
            "revoked_at IS NOT NULL)",
        },
    },
    {
        "table": "core.sso_identity",
        "from": "c1591_check",
        "to": "c1814_check",
        "kind": "CHECK",
        "definition": {
            "table": "core.sso_identity",
            "kind": "CHECK",
            "columns": ["version"],
            "expression": "version>0",
        },
    },
    {
        "table": "core.authentication_throttle",
        "from": "c1592_uk",
        "to": "c1815_uk",
        "kind": "UK",
        "definition": {
            "table": "core.authentication_throttle",
            "kind": "UK",
            "columns": ["bucket_hash", "window_started_at"],
            "expression": "",
        },
    },
    {
        "table": "core.authentication_throttle",
        "from": "c1593_check",
        "to": "c1816_check",
        "kind": "CHECK",
        "definition": {
            "table": "core.authentication_throttle",
            "kind": "CHECK",
            "columns": ["fail_count"],
            "expression": "fail_count>=0",
        },
    },
    {
        "table": "core.authentication_throttle",
        "from": "c1594_idx",
        "to": "c1817_idx",
        "kind": "INDEX",
        "definition": {
            "table": "core.authentication_throttle",
            "kind": "INDEX",
            "columns": ["locked_until"],
            "expression": "",
        },
    },
    {
        "table": "gw.operating_settings",
        "from": "c1595_uk",
        "to": "c1818_uk",
        "kind": "UK",
        "definition": {
            "table": "gw.operating_settings",
            "kind": "UK",
            "columns": ["workspace_id", "generation_id"],
            "expression": "",
        },
    },
    {
        "table": "gw.operating_settings",
        "from": "c1596_check",
        "to": "c1819_check",
        "kind": "CHECK",
        "definition": {
            "table": "gw.operating_settings",
            "kind": "CHECK",
            "columns": ["version"],
            "expression": "version>0",
        },
    },
    {
        "table": "gw.operating_settings",
        "from": "c1597_check",
        "to": "c1820_check",
        "kind": "CHECK",
        "definition": {
            "table": "gw.operating_settings",
            "kind": "CHECK",
            "columns": ["rollout_state"],
            "expression": "rollout_state IN ('DRAFT','PILOT','ACTIVE','PAUSED')",
        },
    },
    {
        "table": "gw.operating_settings",
        "from": "c1598_check",
        "to": "c1821_check",
        "kind": "CHECK",
        "definition": {
            "table": "gw.operating_settings",
            "kind": "CHECK",
            "columns": ["company_hold", "hold_reason"],
            "expression": "NOT company_hold OR (hold_reason IS NOT NULL AND "
            "char_length(btrim(hold_reason)) BETWEEN 2 AND 500)",
        },
    },
    {
        "table": "gw.operating_policy_revision",
        "from": "c1599_uk",
        "to": "c1822_uk",
        "kind": "UK",
        "definition": {
            "table": "gw.operating_policy_revision",
            "kind": "UK",
            "columns": ["workspace_id", "generation_id", "revision_no"],
            "expression": "",
        },
    },
    {
        "table": "gw.operating_policy_revision",
        "from": "c1600_check",
        "to": "c1823_check",
        "kind": "CHECK",
        "definition": {
            "table": "gw.operating_policy_revision",
            "kind": "CHECK",
            "columns": ["expected_people"],
            "expression": "expected_people BETWEEN 1 AND 10000",
        },
    },
    {
        "table": "gw.operating_policy_revision",
        "from": "c1601_check",
        "to": "c1824_check",
        "kind": "CHECK",
        "definition": {
            "table": "gw.operating_policy_revision",
            "kind": "CHECK",
            "columns": ["expected_departments"],
            "expression": "expected_departments BETWEEN 1 AND 1000",
        },
    },
    {
        "table": "gw.operating_policy_revision",
        "from": "c1602_check",
        "to": "c1825_check",
        "kind": "CHECK",
        "definition": {
            "table": "gw.operating_policy_revision",
            "kind": "CHECK",
            "columns": ["backup_interval_minutes"],
            "expression": "backup_interval_minutes BETWEEN 5 AND 1440",
        },
    },
    {
        "table": "gw.operating_policy_revision",
        "from": "c1603_check",
        "to": "c1826_check",
        "kind": "CHECK",
        "definition": {
            "table": "gw.operating_policy_revision",
            "kind": "CHECK",
            "columns": ["rpo_minutes"],
            "expression": "rpo_minutes BETWEEN 1 AND 1440",
        },
    },
    {
        "table": "gw.operating_policy_revision",
        "from": "c1604_check",
        "to": "c1827_check",
        "kind": "CHECK",
        "definition": {
            "table": "gw.operating_policy_revision",
            "kind": "CHECK",
            "columns": ["rto_minutes"],
            "expression": "rto_minutes BETWEEN 15 AND 10080",
        },
    },
    {
        "table": "gw.operating_policy_revision",
        "from": "c1605_check",
        "to": "c1828_check",
        "kind": "CHECK",
        "definition": {
            "table": "gw.operating_policy_revision",
            "kind": "CHECK",
            "columns": ["document_review_months"],
            "expression": "document_review_months BETWEEN 1 AND 120",
        },
    },
    {
        "table": "gw.operating_policy_revision",
        "from": "c1606_check",
        "to": "c1829_check",
        "kind": "CHECK",
        "definition": {
            "table": "gw.operating_policy_revision",
            "kind": "CHECK",
            "columns": ["audit_review_months"],
            "expression": "audit_review_months BETWEEN 1 AND 120",
        },
    },
    {
        "table": "gw.operating_policy_revision",
        "from": "c1607_check",
        "to": "c1830_check",
        "kind": "CHECK",
        "definition": {
            "table": "gw.operating_policy_revision",
            "kind": "CHECK",
            "columns": ["backup_keep_days"],
            "expression": "backup_keep_days BETWEEN 7 AND 365",
        },
    },
    {
        "table": "gw.operating_policy_revision",
        "from": "c1608_check",
        "to": "c1831_check",
        "kind": "CHECK",
        "definition": {
            "table": "gw.operating_policy_revision",
            "kind": "CHECK",
            "columns": ["backup_interval_minutes", "rpo_minutes"],
            "expression": "backup_interval_minutes<rpo_minutes",
        },
    },
    {
        "table": "gw.operating_policy_revision",
        "from": "c1609_check",
        "to": "c1832_check",
        "kind": "CHECK",
        "definition": {
            "table": "gw.operating_policy_revision",
            "kind": "CHECK",
            "columns": ["revision_no"],
            "expression": "revision_no>0",
        },
    },
    {
        "table": "gw.operating_policy_revision",
        "from": "c1610_check",
        "to": "c1833_check",
        "kind": "CHECK",
        "definition": {
            "table": "gw.operating_policy_revision",
            "kind": "CHECK",
            "columns": ["reason"],
            "expression": "char_length(btrim(reason)) BETWEEN 2 AND 500",
        },
    },
    {
        "table": "gw.operating_evidence",
        "from": "c1611_uk",
        "to": "c1834_uk",
        "kind": "UK",
        "definition": {
            "table": "gw.operating_evidence",
            "kind": "UK",
            "columns": ["workspace_id", "generation_id", "run_id"],
            "expression": "",
        },
    },
    {
        "table": "gw.operating_evidence",
        "from": "c1612_check",
        "to": "c1835_check",
        "kind": "CHECK",
        "definition": {
            "table": "gw.operating_evidence",
            "kind": "CHECK",
            "columns": ["kind"],
            "expression": "kind IN ('BACKUP','RESTORE','ACCEPTANCE','INCIDENT')",
        },
    },
    {
        "table": "gw.operating_evidence",
        "from": "c1613_check",
        "to": "c1836_check",
        "kind": "CHECK",
        "definition": {
            "table": "gw.operating_evidence",
            "kind": "CHECK",
            "columns": ["result"],
            "expression": "result IN ('PASS','FAIL','PARTIAL')",
        },
    },
    {
        "table": "gw.operating_evidence",
        "from": "c1614_check",
        "to": "c1837_check",
        "kind": "CHECK",
        "definition": {
            "table": "gw.operating_evidence",
            "kind": "CHECK",
            "columns": ["finished_at", "started_at"],
            "expression": "finished_at>=started_at",
        },
    },
    {
        "table": "gw.retention_review",
        "from": "c1615_uidx",
        "to": "c1838_uidx",
        "kind": "UK_PARTIAL",
        "definition": {
            "table": "gw.retention_review",
            "kind": "UK_PARTIAL",
            "columns": [
                "workspace_id",
                "generation_id",
                "document_id",
                "policy_revision_id",
            ],
            "expression": "UNIQUE WHERE document_id IS NOT NULL",
        },
    },
    {
        "table": "gw.retention_review",
        "from": "c1616_uidx",
        "to": "c1839_uidx",
        "kind": "UK_PARTIAL",
        "definition": {
            "table": "gw.retention_review",
            "kind": "UK_PARTIAL",
            "columns": [
                "workspace_id",
                "generation_id",
                "post_id",
                "policy_revision_id",
            ],
            "expression": "UNIQUE WHERE post_id IS NOT NULL",
        },
    },
    {
        "table": "gw.retention_review",
        "from": "c1617_check",
        "to": "c1840_check",
        "kind": "CHECK",
        "definition": {
            "table": "gw.retention_review",
            "kind": "CHECK",
            "columns": ["document_id", "post_id"],
            "expression": "(document_id IS NULL)<>(post_id IS NULL)",
        },
    },
    {
        "table": "gw.retention_review",
        "from": "c1618_check",
        "to": "c1841_check",
        "kind": "CHECK",
        "definition": {
            "table": "gw.retention_review",
            "kind": "CHECK",
            "columns": ["state"],
            "expression": "state IN ('DUE','HELD','ARCHIVE_PREPARED','ARCHIVED')",
        },
    },
    {
        "table": "gw.retention_review",
        "from": "c1619_check",
        "to": "c1842_check",
        "kind": "CHECK",
        "definition": {
            "table": "gw.retention_review",
            "kind": "CHECK",
            "columns": ["version"],
            "expression": "version>0",
        },
    },
    {
        "table": "gw.retention_review",
        "from": "c1620_check",
        "to": "c1843_check",
        "kind": "CHECK",
        "definition": {
            "table": "gw.retention_review",
            "kind": "CHECK",
            "columns": ["reason"],
            "expression": "char_length(btrim(reason)) BETWEEN 2 AND 500",
        },
    },
    {
        "table": "gw.retention_review",
        "from": "c1621_check",
        "to": "c1844_check",
        "kind": "CHECK",
        "definition": {
            "table": "gw.retention_review",
            "kind": "CHECK",
            "columns": [
                "state",
                "archive_digest",
                "archive_reference",
                "reviewed_by_user_id",
                "reviewed_at",
            ],
            "expression": "state<>'ARCHIVED' OR (archive_digest IS NOT NULL AND "
            "archive_reference IS NOT NULL AND reviewed_by_user_id IS NOT NULL "
            "AND reviewed_at IS NOT NULL)",
        },
    },
    {
        "table": "core.mfa_factor",
        "from": "r524_fk",
        "to": "r598_fk",
        "kind": "FK",
        "definition": {
            "source": "core.mfa_factor",
            "columns": ["user_id"],
            "target": "core.app_user",
            "target_columns": ["id"],
            "on_delete": "RESTRICT",
            "on_update": "RESTRICT",
        },
    },
    {
        "table": "core.authentication_challenge",
        "from": "r525_fk",
        "to": "r599_fk",
        "kind": "FK",
        "definition": {
            "source": "core.authentication_challenge",
            "columns": ["user_id"],
            "target": "core.app_user",
            "target_columns": ["id"],
            "on_delete": "RESTRICT",
            "on_update": "RESTRICT",
        },
    },
    {
        "table": "core.sso_identity",
        "from": "r526_fk",
        "to": "r600_fk",
        "kind": "FK",
        "definition": {
            "source": "core.sso_identity",
            "columns": ["user_id"],
            "target": "core.app_user",
            "target_columns": ["id"],
            "on_delete": "RESTRICT",
            "on_update": "RESTRICT",
        },
    },
    {
        "table": "core.authentication_challenge",
        "from": "r527_fk",
        "to": "r601_fk",
        "kind": "FK",
        "definition": {
            "source": "core.authentication_challenge",
            "columns": ["user_id", "session_id"],
            "target": "core.auth_session",
            "target_columns": ["user_id", "id"],
            "on_delete": "RESTRICT",
            "on_update": "RESTRICT",
        },
    },
    {
        "table": "core.recovery_code",
        "from": "r528_fk",
        "to": "r602_fk",
        "kind": "FK",
        "definition": {
            "source": "core.recovery_code",
            "columns": ["user_id", "factor_id"],
            "target": "core.mfa_factor",
            "target_columns": ["user_id", "id"],
            "on_delete": "RESTRICT",
            "on_update": "RESTRICT",
        },
    },
    {
        "table": "gw.operating_settings",
        "from": "r529_fk",
        "to": "r603_fk",
        "kind": "FK",
        "definition": {
            "source": "gw.operating_settings",
            "columns": ["workspace_id"],
            "target": "core.workspace",
            "target_columns": ["id"],
            "on_delete": "RESTRICT",
            "on_update": "RESTRICT",
        },
    },
    {
        "table": "gw.operating_settings",
        "from": "r530_fk",
        "to": "r604_fk",
        "kind": "FK",
        "definition": {
            "source": "gw.operating_settings",
            "columns": ["workspace_id", "generation_id"],
            "target": "core.data_generation",
            "target_columns": ["workspace_id", "id"],
            "on_delete": "RESTRICT",
            "on_update": "RESTRICT",
        },
    },
    {
        "table": "gw.operating_policy_revision",
        "from": "r531_fk",
        "to": "r605_fk",
        "kind": "FK",
        "definition": {
            "source": "gw.operating_policy_revision",
            "columns": ["workspace_id"],
            "target": "core.workspace",
            "target_columns": ["id"],
            "on_delete": "RESTRICT",
            "on_update": "RESTRICT",
        },
    },
    {
        "table": "gw.operating_policy_revision",
        "from": "r532_fk",
        "to": "r606_fk",
        "kind": "FK",
        "definition": {
            "source": "gw.operating_policy_revision",
            "columns": ["workspace_id", "generation_id"],
            "target": "core.data_generation",
            "target_columns": ["workspace_id", "id"],
            "on_delete": "RESTRICT",
            "on_update": "RESTRICT",
        },
    },
    {
        "table": "gw.operating_evidence",
        "from": "r533_fk",
        "to": "r607_fk",
        "kind": "FK",
        "definition": {
            "source": "gw.operating_evidence",
            "columns": ["workspace_id"],
            "target": "core.workspace",
            "target_columns": ["id"],
            "on_delete": "RESTRICT",
            "on_update": "RESTRICT",
        },
    },
    {
        "table": "gw.operating_evidence",
        "from": "r534_fk",
        "to": "r608_fk",
        "kind": "FK",
        "definition": {
            "source": "gw.operating_evidence",
            "columns": ["workspace_id", "generation_id"],
            "target": "core.data_generation",
            "target_columns": ["workspace_id", "id"],
            "on_delete": "RESTRICT",
            "on_update": "RESTRICT",
        },
    },
    {
        "table": "gw.retention_review",
        "from": "r535_fk",
        "to": "r609_fk",
        "kind": "FK",
        "definition": {
            "source": "gw.retention_review",
            "columns": ["workspace_id"],
            "target": "core.workspace",
            "target_columns": ["id"],
            "on_delete": "RESTRICT",
            "on_update": "RESTRICT",
        },
    },
    {
        "table": "gw.retention_review",
        "from": "r536_fk",
        "to": "r610_fk",
        "kind": "FK",
        "definition": {
            "source": "gw.retention_review",
            "columns": ["workspace_id", "generation_id"],
            "target": "core.data_generation",
            "target_columns": ["workspace_id", "id"],
            "on_delete": "RESTRICT",
            "on_update": "RESTRICT",
        },
    },
    {
        "table": "gw.operating_settings",
        "from": "r537_fk",
        "to": "r611_fk",
        "kind": "FK",
        "definition": {
            "source": "gw.operating_settings",
            "columns": ["workspace_id", "generation_id", "current_policy_revision_id"],
            "target": "gw.operating_policy_revision",
            "target_columns": ["workspace_id", "generation_id", "id"],
            "on_delete": "RESTRICT",
            "on_update": "RESTRICT",
        },
    },
    {
        "table": "gw.operating_policy_revision",
        "from": "r538_fk",
        "to": "r612_fk",
        "kind": "FK",
        "definition": {
            "source": "gw.operating_policy_revision",
            "columns": ["workspace_id", "generation_id", "responsible_person_id"],
            "target": "gw.person",
            "target_columns": ["workspace_id", "generation_id", "id"],
            "on_delete": "RESTRICT",
            "on_update": "RESTRICT",
        },
    },
    {
        "table": "gw.operating_evidence",
        "from": "r539_fk",
        "to": "r613_fk",
        "kind": "FK",
        "definition": {
            "source": "gw.operating_evidence",
            "columns": ["workspace_id", "generation_id", "policy_revision_id"],
            "target": "gw.operating_policy_revision",
            "target_columns": ["workspace_id", "generation_id", "id"],
            "on_delete": "RESTRICT",
            "on_update": "RESTRICT",
        },
    },
    {
        "table": "gw.retention_review",
        "from": "r540_fk",
        "to": "r614_fk",
        "kind": "FK",
        "definition": {
            "source": "gw.retention_review",
            "columns": ["workspace_id", "generation_id", "policy_revision_id"],
            "target": "gw.operating_policy_revision",
            "target_columns": ["workspace_id", "generation_id", "id"],
            "on_delete": "RESTRICT",
            "on_update": "RESTRICT",
        },
    },
    {
        "table": "gw.retention_review",
        "from": "r541_fk",
        "to": "r615_fk",
        "kind": "FK",
        "definition": {
            "source": "gw.retention_review",
            "columns": ["workspace_id", "generation_id", "document_id"],
            "target": "gw.approval_document",
            "target_columns": ["workspace_id", "generation_id", "id"],
            "on_delete": "RESTRICT",
            "on_update": "RESTRICT",
        },
    },
    {
        "table": "gw.retention_review",
        "from": "r542_fk",
        "to": "r616_fk",
        "kind": "FK",
        "definition": {
            "source": "gw.retention_review",
            "columns": ["workspace_id", "generation_id", "post_id"],
            "target": "gw.board_post",
            "target_columns": ["workspace_id", "generation_id", "id"],
            "on_delete": "RESTRICT",
            "on_update": "RESTRICT",
        },
    },
]


def ident(value):
    return '"' + value.replace('"', '""') + '"'


def qualified(value):
    return ".".join(ident(v) for v in value.split("."))


def mismatch(table, name):
    raise RuntimeError(f"GW_INTEGRATION_OBJECT_MISMATCH: {table}.{name}")


def columns(connection, relation, numbers):
    return list(
        connection.scalars(
            text("""SELECT a.attname FROM unnest(CAST(:numbers AS smallint[])) WITH ORDINALITY k(num,seq)
        JOIN pg_attribute a ON a.attrelid=CAST(:relation AS oid) AND a.attnum=k.num ORDER BY k.seq"""),
            {"numbers": numbers, "relation": relation},
        )
    )


def predicate(connection, table, expression, temps):
    if not expression:
        return None
    if table not in temps:
        name = "gw_merge_" + uuid4().hex
        connection.exec_driver_sql(
            f"CREATE TEMP TABLE {ident(name)} (LIKE {qualified(table)}) ON COMMIT DROP"
        )
        temps[table] = "pg_temp." + name
    name = "c_" + uuid4().hex
    temp = temps[table]
    connection.exec_driver_sql(
        f"ALTER TABLE {qualified(temp)} ADD CONSTRAINT {ident(name)} CHECK ({expression})"
    )
    return connection.scalar(
        text(
            "SELECT pg_get_expr(conbin,conrelid) FROM pg_constraint WHERE conrelid=to_regclass(:table) AND conname=:name"
        ),
        {"table": temp, "name": name},
    )


def inspect_object(connection, item, name, temps):
    table, kind, expected = item["table"], item["kind"], item["definition"]
    if kind in {"INDEX", "UK_PARTIAL", "UNIQUE_INDEX"}:
        row = (
            connection.execute(
                text("""SELECT i.indexrelid AS oid,i.indrelid,i.indkey::smallint[] AS keys,
            i.indisvalid,i.indisready,i.indislive,i.indisunique,i.indnatts,i.indnkeyatts,
            i.indnullsnotdistinct,
            NOT EXISTS(SELECT 1 FROM unnest(i.indclass::oid[],i.indcollation::oid[],i.indkey::smallint[],i.indoption::smallint[]) k(opclass_oid,collation_oid,attnum,options)
              JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum
              JOIN pg_opclass p ON p.oid=k.opclass_oid
              WHERE NOT p.opcdefault OR k.collation_oid<>a.attcollation OR k.options<>0) AS default_options,
            pg_get_expr(i.indpred,i.indrelid) AS predicate,am.amname
            FROM pg_index i JOIN pg_class x ON x.oid=i.indexrelid
            JOIN pg_am am ON am.oid=x.relam
            WHERE i.indexrelid=to_regclass(:name) AND i.indrelid=to_regclass(:table)"""),
                {"table": table, "name": table.split(".")[0] + "." + name},
            )
            .mappings()
            .one_or_none()
        )
        if not row:
            mismatch(table, name)
        expression = expected["expression"]
        if kind in {"UK_PARTIAL", "UNIQUE_INDEX"}:
            expression = re.split(
                r"\bWHERE\b", expression, maxsplit=1, flags=re.IGNORECASE
            )[1].strip()
        if not (
            row["indisvalid"]
            and row["indisready"]
            and row["indislive"]
            and row["amname"] == "btree"
            and row["default_options"]
            and not row["indnullsnotdistinct"]
            and row["indisunique"] == (kind != "INDEX")
            and row["indnatts"] == row["indnkeyatts"] == len(expected["columns"])
            and columns(connection, row["indrelid"], row["keys"]) == expected["columns"]
            and row["predicate"] == predicate(connection, table, expression, temps)
        ):
            mismatch(table, name)
        return (row["oid"],)
    row = (
        connection.execute(
            text("""SELECT c.oid,c.conrelid,c.conkey,c.confrelid,c.confkey,c.contype,
        c.convalidated,c.condeferrable,c.condeferred,c.connoinherit,c.confdeltype,c.confupdtype,c.confmatchtype,
        c.conindid,pg_get_expr(c.conbin,c.conrelid) AS expression,
        x.relname AS index_name,i.indisvalid,i.indisready,i.indisunique,i.indnullsnotdistinct,
        tn.nspname || '.' || tc.relname AS target
        FROM pg_constraint c LEFT JOIN pg_class tc ON tc.oid=c.confrelid
        LEFT JOIN pg_namespace tn ON tn.oid=tc.relnamespace
        LEFT JOIN pg_class x ON x.oid=c.conindid
        LEFT JOIN pg_index i ON i.indexrelid=c.conindid
        WHERE c.conrelid=to_regclass(:table) AND c.conname=:name"""),
            {"table": table, "name": name},
        )
        .mappings()
        .one_or_none()
    )
    code = {"PK": "p", "UK": "u", "CHECK": "c", "FK": "f"}[kind]
    if (
        not row
        or row["contype"] != code
        or not row["convalidated"]
        or row["condeferrable"]
        or row["condeferred"]
        or (kind == "CHECK" and row["connoinherit"])
    ):
        mismatch(table, name)
    if (
        kind != "CHECK"
        and columns(connection, row["conrelid"], row["conkey"]) != expected["columns"]
    ):
        mismatch(table, name)
    if kind in {"PK", "UK"} and not (
        row["index_name"] == name
        and row["indisvalid"]
        and row["indisready"]
        and row["indisunique"]
        and not row["indnullsnotdistinct"]
    ):
        mismatch(table, name)
    if kind == "CHECK" and row["expression"] != predicate(
        connection, table, expected["expression"], temps
    ):
        mismatch(table, name)
    if kind == "FK" and not (
        row["target"] == expected["target"]
        and columns(connection, row["confrelid"], row["confkey"])
        == expected["target_columns"]
        and row["confdeltype"] == "r"
        and row["confupdtype"] == "r"
        and row["confmatchtype"] == "s"
    ):
        mismatch(table, name)
    return (row["oid"], row["conindid"])


def rename(reverse=False):
    connection = op.get_bind()
    items = list(reversed(RENAMES)) if reverse else RENAMES
    for table in sorted({v["table"] for v in items}):
        connection.exec_driver_sql(
            f"LOCK TABLE {qualified(table)} IN ACCESS EXCLUSIVE MODE"
        )
    temps = {}
    before = []
    for item in items:
        old, new = (item["to"], item["from"]) if reverse else (item["from"], item["to"])
        # Validate the complete set before issuing even the first persistent rename.
        before.append(inspect_object(connection, item, old, temps))
        if connection.scalar(
            text(
                "SELECT EXISTS(SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass(:table) AND conname=:name)"
            ),
            {"table": item["table"], "name": new},
        ):
            mismatch(item["table"], new)
        if (
            item["kind"] in {"PK", "UK", "INDEX", "UK_PARTIAL", "UNIQUE_INDEX"}
            and connection.scalar(
                text("SELECT to_regclass(:name)"),
                {"name": item["table"].split(".")[0] + "." + new},
            )
            is not None
        ):
            mismatch(item["table"], new)
    for item in items:
        old, new = (item["to"], item["from"]) if reverse else (item["from"], item["to"])
        if item["kind"] in {"INDEX", "UK_PARTIAL", "UNIQUE_INDEX"}:
            connection.exec_driver_sql(
                f"ALTER INDEX {qualified(item['table'].split('.')[0] + '.' + old)} RENAME TO {ident(new)}"
            )
        else:
            connection.exec_driver_sql(
                f"ALTER TABLE {qualified(item['table'])} RENAME CONSTRAINT {ident(old)} TO {ident(new)}"
            )
    for item, identity in zip(items, before, strict=True):
        name = item["from"] if reverse else item["to"]
        if inspect_object(connection, item, name, temps) != identity:
            mismatch(item["table"], name)


def upgrade():
    rename()


def downgrade():
    # Name-only inverse. Parent downgrades keep their security-history guards.
    rename(reverse=True)

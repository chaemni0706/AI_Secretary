"""SQLAlchemy ORM model for the AI 가계부 (ledger) feature.

Deliberately kept in a SEPARATE module from ``models.py`` so the planner
(EVENT/TODO) domain contract in ``models.py`` — "No new tables … only existing
tables" — is not touched. This model shares the same declarative ``Base`` as
``models.py`` and maps the ``ledger_transactions`` table appended to
``database/local_schema.sql``.

Conventions (matching local_schema.sql / models.py):
- enum-like columns store UPPERCASE CHECK values; the API/Pydantic layer
  translates to/from lowercase (see ``ledger_schema``).
- ``amount`` is an INTEGER in KRW (won).
- ``occurred_at`` is an ISO datetime string; ``date`` ('YYYY-MM-DD') and
  ``time`` ('HH:MM') are stored separately for indexed calendar aggregation.
- array-ish data (``items``, ``alternatives``) is stored as JSON TEXT.
- the table is created from local_schema.sql (raw SQL, IF NOT EXISTS), never
  via ``Base.metadata.create_all``.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, Float, ForeignKey, Integer, String, Text

from backend.database.models import Base

# --- Allowed CHECK values (UPPERCASE, matching local_schema.sql) -------------
LEDGER_SOURCE_TYPE_VALUES = ("NOTIFICATION", "RECEIPT_SCAN", "MANUAL", "SEED")
LEDGER_TX_TYPE_VALUES = ("EXPENSE", "INCOME", "CANCEL", "IGNORE")
LEDGER_STATUS_VALUES = ("PENDING", "CONFIRMED", "DUPLICATE", "DELETED", "NEEDS_REVIEW")


class LedgerTransaction(Base):
    __tablename__ = "ledger_transactions"

    transaction_id = Column(String, primary_key=True)
    user_id = Column(
        String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )

    source_type = Column(String, nullable=False)
    app_name = Column(String)
    title = Column(String)
    raw_text = Column(Text)

    merchant = Column(String)
    normalized_merchant = Column(String)
    amount = Column(Integer, nullable=False, default=0)
    transaction_type = Column(String, nullable=False)

    category = Column(String)
    category_source = Column(String)
    confidence = Column(Float)
    needs_user_confirmation = Column(Integer, nullable=False, default=0)
    alternatives_json = Column(Text)

    occurred_at = Column(String)
    date = Column(String)
    time = Column(String)

    status = Column(String, nullable=False, default="PENDING")
    duplicated_transaction_id = Column(String)  # app-layer managed, no FK
    dedup_key = Column(String)
    source_hash = Column(String)

    items_json = Column(Text)
    is_recurring = Column(Integer, nullable=False, default=0)

    memo = Column(Text)  # 사용자 자유 메모(선택)

    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('NOTIFICATION','RECEIPT_SCAN','MANUAL','SEED')",
            name="ck_ledger_source_type",
        ),
        CheckConstraint(
            "transaction_type IN ('EXPENSE','INCOME','CANCEL','IGNORE')",
            name="ck_ledger_tx_type",
        ),
        CheckConstraint(
            "status IN ('PENDING','CONFIRMED','DUPLICATE','DELETED','NEEDS_REVIEW')",
            name="ck_ledger_status",
        ),
    )

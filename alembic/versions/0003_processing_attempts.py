"""count processing attempts on the payment"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_processing_attempts"
down_revision: str | None = "0002_operations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("processing_attempts", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("payments", "processing_attempts")

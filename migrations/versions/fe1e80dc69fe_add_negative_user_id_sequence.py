"""add_negative_user_id_sequence

Revision ID: fe1e80dc69fe
Revises: 460f372be359
Create Date: 2025-03-20 10:42:56.690608

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "fe1e80dc69fe"
down_revision = "460f372be359"
branch_labels = None
depends_on = None


def upgrade():
    # Add 'anonymized' to the UserAccountStatus enum
    # The enum is non-native (native_enum=False as per migration 4daee978090a),
    # so we need to modify the CHECK constraint
    op.execute(
        """
        ALTER TABLE "user" DROP CONSTRAINT IF EXISTS useraccountstatus;
        """
    )

    op.execute(
        """
        ALTER TABLE "user" ADD CONSTRAINT useraccountstatus 
        CHECK (status IN ('active', 'blocked_bad_password', 'third_party_pending_approval', 'anonymized'));
        """
    )

    op.execute(
        """
        CREATE SEQUENCE IF NOT EXISTS negative_user_id_seq
        START WITH -1
        INCREMENT BY -1
        NO MINVALUE
        NO MAXVALUE
        CACHE 1;
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_status_anonymized ON "user" (status)
        WHERE status = 'anonymized';
        """
    )

    op.execute(
        """
        DROP TABLE anon_user;
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_user_status_anonymized;")
    op.execute("DROP SEQUENCE IF EXISTS negative_user_id_seq;")

"""add acr and amr columns for authlib 1.6.3

Revision ID: 1c6085670a9f
Revises: c1e0cfacea5a
Create Date: 2025-12-10 12:57:52.908562

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1c6085670a9f"
down_revision = "c1e0cfacea5a"
branch_labels = None
depends_on = None


def upgrade():
    # Authlib 1.6.3 adds acr (Authentication Context Class Reference) and
    # amr (Authentication Methods References) columns to OAuth2AuthorizationCodeMixin
    # See: https://gist.github.com/lepture/506bfc29b827fae87981fc58eff2393e
    op.add_column(
        "oauth2_authorization_code", sa.Column("acr", sa.Text(), nullable=True)
    )
    op.add_column(
        "oauth2_authorization_code", sa.Column("amr", sa.Text(), nullable=True)
    )


def downgrade():
    op.drop_column("oauth2_authorization_code", "amr")
    op.drop_column("oauth2_authorization_code", "acr")

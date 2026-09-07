"""Deck trash, source imports, immutable versions and saved pods."""
from alembic import op
import sqlalchemy as sa
revision='0002'
down_revision='0001'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('decks',sa.Column('deleted_at',sa.String(),nullable=True))
    for name in ('source_url','sideboard','maybeboard'):
        op.add_column('decks',sa.Column(name,sa.String(),nullable=False,server_default=''))
    common=lambda:[sa.Column('id',sa.String(),primary_key=True),sa.Column('created_at',sa.String(),nullable=False),sa.Column('updated_at',sa.String(),nullable=False)]
    op.create_table('deck_versions',*common(),sa.Column('deck_id',sa.String(),sa.ForeignKey('decks.id'),nullable=False),*[sa.Column(n,sa.String(),nullable=False) for n in ('name','commanders','color_identity','decklist','sideboard','maybeboard')])
    op.create_table('saved_pods',*common(),sa.Column('name',sa.String(),nullable=False),sa.Column('player_ids',sa.JSON(),nullable=False))
    # SQLite supports adding a nullable REFERENCES column without rebuilding history.
    op.execute('ALTER TABLE participants ADD COLUMN deck_version_id VARCHAR REFERENCES deck_versions(id)')
    # Old games have no known version: deliberately leave their version unset.

def downgrade():
    op.drop_column('participants','deck_version_id')
    op.drop_table('saved_pods')
    op.drop_table('deck_versions')
    for name in ('deleted_at','source_url','sideboard','maybeboard'): op.drop_column('decks',name)

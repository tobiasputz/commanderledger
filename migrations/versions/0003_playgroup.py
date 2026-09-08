"""Live play, feedback, analysis, seasons, leagues and audit records."""
from alembic import op
import sqlalchemy as sa
revision='0003'
down_revision='0002'
branch_labels=None
depends_on=None

def cols():
    return [sa.Column('id',sa.String(),primary_key=True),sa.Column('created_at',sa.String(),nullable=False),sa.Column('updated_at',sa.String(),nullable=False)]
def string(name,nullable=False): return sa.Column(name,sa.String(),nullable=nullable)
def js(name): return sa.Column(name,sa.JSON(),nullable=False)
def ref(name,target,nullable=False,unique=False):return sa.Column(name,sa.String(),sa.ForeignKey(target),nullable=nullable,unique=unique)
def upgrade():
    op.create_table('live_games',*cols(),string('name'),js('state'),sa.Column('revision',sa.Integer(),nullable=False),ref('game_id','games.id',True))
    op.create_table('seasons',*cols(),*[string(k) for k in ('name','date_from','date_to')])
    op.create_table('leagues',*cols(),string('name'),js('player_ids'),js('scoring'),sa.Column('archived',sa.Boolean(),nullable=False))
    op.create_table('league_rounds',*cols(),ref('league_id','leagues.id'),sa.Column('number',sa.Integer(),nullable=False),sa.Column('locked',sa.Boolean(),nullable=False),*[js(k) for k in ('pairings','byes','results','scoring')],sa.UniqueConstraint('league_id','number'))
    op.create_table('feedback',*cols(),ref('game_id','games.id'),ref('player_id','players.id'),sa.Column('confirmed',sa.Boolean(),nullable=False),js('values'),sa.UniqueConstraint('game_id','player_id'))
    op.create_table('deck_analysis',*cols(),ref('deck_id','decks.id',unique=True),string('status'),string('source_hash'),js('result'),js('overrides'),string('error'))
    op.create_table('source_checks',*cols(),ref('deck_id','decks.id',unique=True),js('payload'),string('source_hash'),string('error'))
    op.create_table('audit_log',*cols(),*[string(k) for k in ('actor','action','entity','entity_id')],js('before'),js('after'))
def downgrade():
    for table in ('audit_log','source_checks','deck_analysis','feedback','league_rounds','leagues','seasons','live_games'):op.drop_table(table)

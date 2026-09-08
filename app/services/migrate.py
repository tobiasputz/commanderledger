from alembic.config import Config
from alembic import command
from app.db import ROOT,engine
from sqlalchemy import inspect,text

def initialize() -> None:
    inspector=inspect(engine)
    if 'alembic_version' in inspector.get_table_names():
        with engine.connect() as conn:
            if conn.execute(text('SELECT version_num FROM alembic_version')).scalar()=='0003': return
    command.upgrade(Config(str(ROOT/'alembic.ini')),'head')

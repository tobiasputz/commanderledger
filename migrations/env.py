from alembic import context
from sqlalchemy import create_engine
from app.models import Base
from app.db import DB_PATH
from app.services.backup import backup_database
config=context.config
url=config.attributes.get('url','sqlite:///'+str(DB_PATH))
if context.is_offline_mode():
    context.configure(url=url,target_metadata=Base.metadata,literal_binds=True)
    with context.begin_transaction(): context.run_migrations()
else:
    engine=create_engine(url)
    if url.startswith('sqlite:///'):
        from pathlib import Path
        backup_database(source=Path(url.removeprefix('sqlite:///')))
    with engine.connect() as connection:
        context.configure(connection=connection,target_metadata=Base.metadata,render_as_batch=True)
        with context.begin_transaction(): context.run_migrations()

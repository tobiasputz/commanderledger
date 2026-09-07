from pathlib import Path
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from collections.abc import Generator
load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv('COMMANDER_DB', str(ROOT / 'data' / 'commander.db'))).resolve()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
engine = create_engine('sqlite:///' + str(DB_PATH), connect_args={'check_same_thread': False})
@event.listens_for(engine, 'connect')
def configure_sqlite(connection: object, _: object) -> None:
    connection.execute('PRAGMA foreign_keys=ON')
    connection.execute('PRAGMA busy_timeout=5000')
SessionLocal = sessionmaker(engine, expire_on_commit=False)
def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session

import asyncio,json,os
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import select
from app.models import Setting,Deck,SourceCheck
from app.services.backup import export_json

def directory():
    from app.db import ROOT
    path=Path(os.getenv('COMMANDER_BACKUPS',str(ROOT/'backups'))).resolve();path.mkdir(parents=True,exist_ok=True);return path

def daily_backup(factory):
    today=datetime.now(timezone.utc).strftime('%Y%m%d');path=directory()/('scheduled-'+today+'.json')
    if path.exists():return
    with factory() as db:
        payload=export_json(db)
        temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8');temporary.replace(path)
    # Retain 30 scheduled snapshots. Manual and migration backups are never pruned.
    for old in sorted(directory().glob('scheduled-*.json'),reverse=True)[30:]:old.unlink()

def tick(factory):
    daily_backup(factory)
    with factory() as db:
        enabled=db.get(Setting,'auto_source_checks')
        if not enabled or not enabled.value:return
        for deck in db.scalars(select(Deck).where(Deck.deleted_at.is_(None),Deck.source_url!='')):
            check=db.scalar(select(SourceCheck).where(SourceCheck.deck_id==deck.id))
            if check:
                stamp=datetime.fromisoformat(check.updated_at).replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc)-stamp).total_seconds()<86400:continue
            from app.services.analysis import check_source
            check_source(deck.id,factory);break

async def loop(factory):
    while True:
        try:await asyncio.to_thread(tick,factory)
        except Exception:
            import logging
            logging.getLogger('commander.maintenance').exception('Scheduled maintenance failed')
        await asyncio.sleep(60)

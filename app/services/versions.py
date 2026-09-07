from sqlalchemy import select
from app.models import DeckVersion
FIELDS=('commanders','color_identity','decklist','sideboard','maybeboard')

def latest(db, deck):
    return db.scalar(select(DeckVersion).where(DeckVersion.deck_id==deck.id).order_by(DeckVersion.created_at.desc(),DeckVersion.id.desc()))

def snapshot(db, deck, name=None):
    previous=latest(db,deck)
    values={k:getattr(deck,k) for k in FIELDS}
    if previous and not name and all(getattr(previous,k)==v for k,v in values.items()): return previous
    version=DeckVersion(deck_id=deck.id,name=name or ('Initial version' if not previous else 'Updated deck'),**values)
    db.add(version);db.flush()
    return version

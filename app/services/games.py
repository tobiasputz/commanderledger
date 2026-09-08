from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Game, Participant, Player, Deck, Location, Event, Rating, Ownership, Feedback, now, uid
from app.schemas import GameInput, RatingInput

def require(db: Session, model: type, identity: str) -> object:
    obj=db.get(model,identity)
    if obj is None: raise HTTPException(404, f'{model.__name__} not found')
    return obj

def save_game(db: Session, data: GameInput, identity: str | None = None) -> Game:
    if identity:
        from app.services.leagues import guard_game
        guard_game(db,identity)
    duplicate=db.scalar(select(Game).where(Game.submission_key==data.submission_key))
    if duplicate and not identity: return duplicate
    if duplicate and duplicate.id != identity: raise HTTPException(409,'Submission key belongs to another game')
    game=require(db,Game,identity) if identity else Game(id=uid())
    old={p.id:p for p in game.participants} if identity else {}
    if data.location_id: require(db,Location,data.location_id)
    if data.event_id: require(db,Event,data.event_id)
    values=data.model_dump(exclude={'participants','overall_rating','deck_ratings','sportsmanship'})
    values['played_at']=data.played_at.isoformat()
    for k,v in values.items(): setattr(game,k,v)
    db.add(game)
    # Free seat uniqueness temporarily so exchanging seats is safe within this transaction.
    if identity:
        for p in old.values(): p.seat+=100
        db.flush()
    kept=[]
    for raw in data.participants:
        p=old.get(raw.id) if raw.id else None
        if raw.id and not p: raise HTTPException(400,'Participant does not belong to this game')
        unchanged=p is not None and p.player_id==raw.player_id and p.deck_id==raw.deck_id
        if not p: p=Participant(id=uid(),game_id=game.id)
        values=raw.model_dump(exclude={'id'})
        if raw.player_id:
            player=require(db,Player,raw.player_id)
            values['player_name']=p.player_name if unchanged else player.name
        else: values['player_name']=raw.player_name or f'LGS random {raw.seat}'
        if raw.deck_id:
            deck=require(db,Deck,raw.deck_id)
            if deck.deleted_at and not unchanged: raise HTTPException(409,'This deck is in Trash. Restore it or choose another deck.')
            from app.models import DeckVersion
            if raw.deck_version_id:
                version=require(db,DeckVersion,raw.deck_version_id)
                if version.deck_id!=deck.id: raise HTTPException(400,'Version belongs to another deck.')
                values['deck_version_id']=version.id
            elif unchanged:
                values['deck_version_id']=p.deck_version_id
            else:
                from app.services.versions import snapshot
                values['deck_version_id']=snapshot(db,deck).id
            if unchanged:
                for k in ('deck_name','commanders','archetype','deck_links'): values[k]=getattr(p,k)
            else:
                values.update(deck_name=deck.name,commanders=deck.commanders,archetype=deck.archetype,deck_links=deck.links)
                from datetime import datetime, timezone
                played=data.played_at.replace(tzinfo=data.played_at.tzinfo or timezone.utc)
                def at(value: str) -> datetime:
                    parsed=datetime.fromisoformat(value)
                    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc)
                history=list(db.scalars(select(Ownership).where(Ownership.deck_id==deck.id)))
                historical=next((h for h in history if at(h.started_at)<=played and (not h.ended_at or played<at(h.ended_at))),None)
                p.owner_id_snapshot=historical.owner_id if historical else deck.owner_id
                p.owner_name=require(db,Player,p.owner_id_snapshot).name
        elif not unchanged:
            if raw.deck_version_id: raise HTTPException(400,'A version requires a permanent deck.')
            p.owner_id_snapshot=None
            p.owner_name=''
        if raw.deck_id and values.get('deck_version_id') and (not unchanged or raw.deck_version_id and raw.deck_version_id!=p.deck_version_id):
            version=require(db,DeckVersion,values['deck_version_id'])
            values['commanders']=version.commanders
        for k,v in values.items(): setattr(p,k,v)
        kept.append(p)
    removed=set(old)-{p.id for p in kept}
    if identity:
        old_players={p.player_id for p in old.values() if p.player_id}
        new_players={p.player_id for p in kept if p.player_id}
        if old_players!=new_players:
            feedback=list(db.scalars(select(Feedback).where(Feedback.game_id==identity)))
            feedback_authors={row.player_id for row in feedback}
            # A seat change invalidates the sealed group-feedback set and its published ratings.
            for row in feedback: db.delete(row)
            for rating in db.scalars(select(Rating).where(Rating.game_id==identity,Rating.rater_id.in_(feedback_authors))):
                db.delete(rating)
    # Ratings tied to removed seats are deleted; ratings on retained seats remain.
    for r in list(game.ratings):
        if r.participant_id in removed:
            game.ratings.remove(r)
    db.flush()
    game.participants=kept
    db.flush()
    # Quick-entry ratings belong to the app owner (rater NULL).
    for kind,value,participant_id in [('overall',data.overall_rating,None),('sportsmanship',data.sportsmanship,None)]+[('deck',data.deck_ratings.get(p.seat),p.id) for p in kept]:
        existing=next((r for r in game.ratings if r.kind==kind and r.participant_id==participant_id and r.rater_id is None),None)
        if value is None:
            if existing: game.ratings.remove(existing)
        elif existing: existing.value=value
        else: game.ratings.append(Rating(game_id=game.id,participant_id=participant_id,kind=kind,value=value))
    game.updated_at=now()
    db.flush()
    return game

def save_rating(db: Session, data: RatingInput) -> Rating:
    game=require(db,Game,data.game_id)
    if data.rater_id and data.rater_id not in {p.player_id for p in game.participants}: raise HTTPException(400,'Named rater must participate in the game')
    if data.kind=='deck':
        target=next((p for p in game.participants if p.id==data.participant_id),None)
        if not target: raise HTTPException(400,'Choose a deck seat from this game')
        if data.rater_id and target.player_id==data.rater_id: raise HTTPException(400,'Opponent deck ratings cannot rate your own seat')
    elif data.participant_id: raise HTTPException(400,'Only deck ratings have a target seat')
    existing=db.scalar(select(Rating).where(Rating.game_id==data.game_id,Rating.kind==data.kind,Rating.participant_id==data.participant_id,Rating.rater_id==data.rater_id))
    obj=existing or Rating()
    for k,v in data.model_dump().items(): setattr(obj,k,v)
    db.add(obj); db.flush()
    return obj

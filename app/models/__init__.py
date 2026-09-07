"""Relational identities plus immutable-at-entry historical participant snapshots."""
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any
from sqlalchemy import String, ForeignKey, JSON, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def uid() -> str:
    return str(uuid4())

class Base(DeclarativeBase):
    pass

class Record:
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    created_at: Mapped[str] = mapped_column(default=now)
    updated_at: Mapped[str] = mapped_column(default=now, onupdate=now)

class Player(Record, Base):
    __tablename__ = 'players'
    name: Mapped[str]
    preferred_name: Mapped[str] = mapped_column(default='')
    notes: Mapped[str] = mapped_column(default='')
    color: Mapped[str] = mapped_column(default='#a995ef')
    archived: Mapped[bool] = mapped_column(default=False)

class Deck(Record, Base):
    __tablename__ = 'decks'
    name: Mapped[str]
    owner_id: Mapped[str] = mapped_column(ForeignKey('players.id'))
    commanders: Mapped[str]
    color_identity: Mapped[str] = mapped_column(default='')
    archetype: Mapped[str] = mapped_column(default='')
    bracket: Mapped[int | None]
    budget: Mapped[float | None]
    notes: Mapped[str] = mapped_column(default='')
    status: Mapped[str] = mapped_column(default='active')
    deleted_at: Mapped[str | None]
    source_url: Mapped[str] = mapped_column(default='')
    sideboard: Mapped[str] = mapped_column(default='')
    maybeboard: Mapped[str] = mapped_column(default='')
    retired_at: Mapped[str | None]
    links: Mapped[list] = mapped_column(JSON, default=list)
    decklist: Mapped[str] = mapped_column(default='')
    color: Mapped[str] = mapped_column(default='#89cbb1')
    __table_args__ = (CheckConstraint("status IN ('active','retired','dismantled')"),)

class DeckVersion(Record, Base):
    __tablename__ = 'deck_versions'
    deck_id: Mapped[str] = mapped_column(ForeignKey('decks.id'))
    name: Mapped[str]
    commanders: Mapped[str]
    color_identity: Mapped[str] = mapped_column(default='')
    decklist: Mapped[str] = mapped_column(default='')
    sideboard: Mapped[str] = mapped_column(default='')
    maybeboard: Mapped[str] = mapped_column(default='')

class SavedPod(Record, Base):
    __tablename__ = 'saved_pods'
    name: Mapped[str]
    player_ids: Mapped[list] = mapped_column(JSON, default=list)

class Ownership(Record, Base):
    __tablename__ = 'ownerships'
    deck_id: Mapped[str] = mapped_column(ForeignKey('decks.id'))
    owner_id: Mapped[str] = mapped_column(ForeignKey('players.id'))
    started_at: Mapped[str] = mapped_column(default=now)
    ended_at: Mapped[str | None]

class Location(Record, Base):
    __tablename__ = 'locations'
    name: Mapped[str]
    notes: Mapped[str] = mapped_column(default='')
    archived: Mapped[bool] = mapped_column(default=False)

class Event(Record, Base):
    __tablename__ = 'events'
    name: Mapped[str]
    notes: Mapped[str] = mapped_column(default='')
    archived: Mapped[bool] = mapped_column(default=False)

class Game(Record, Base):
    __tablename__ = 'games'
    played_at: Mapped[str]
    location_id: Mapped[str | None] = mapped_column(ForeignKey('locations.id'))
    event_id: Mapped[str | None] = mapped_column(ForeignKey('events.id'))
    setting: Mapped[str] = mapped_column(default='home')
    result: Mapped[str]
    duration: Mapped[int | None]
    turns: Mapped[int | None]
    ending: Mapped[str] = mapped_column(default='')
    notes: Mapped[str] = mapped_column(default='')
    memorable: Mapped[str] = mapped_column(default='')
    tags: Mapped[list] = mapped_column(JSON, default=list)
    deleted: Mapped[bool] = mapped_column(default=False)
    submission_key: Mapped[str] = mapped_column(unique=True)
    participants: Mapped[list['Participant']] = relationship(cascade='all, delete-orphan', lazy='selectin')
    ratings: Mapped[list['Rating']] = relationship(cascade='all, delete-orphan', lazy='selectin')
    __table_args__ = (CheckConstraint("result IN ('win','shared','draw','abandoned','no_contest','unknown')"), CheckConstraint('duration IS NULL OR duration > 0'), CheckConstraint('turns IS NULL OR turns > 0'))

class Participant(Record, Base):
    __tablename__ = 'participants'
    game_id: Mapped[str] = mapped_column(ForeignKey('games.id', ondelete='CASCADE'))
    player_id: Mapped[str | None] = mapped_column(ForeignKey('players.id'))
    deck_id: Mapped[str | None] = mapped_column(ForeignKey('decks.id'))
    deck_version_id: Mapped[str | None] = mapped_column(ForeignKey('deck_versions.id'))
    owner_id_snapshot: Mapped[str | None] = mapped_column(ForeignKey('players.id'))
    player_name: Mapped[str]
    deck_name: Mapped[str]
    commanders: Mapped[str]
    owner_name: Mapped[str] = mapped_column(default='')
    archetype: Mapped[str] = mapped_column(default='')
    deck_links: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(default='')
    seat: Mapped[int]
    starting: Mapped[bool] = mapped_column(default=False)
    winner: Mapped[bool] = mapped_column(default=False)
    elimination: Mapped[int | None]
    __table_args__ = (UniqueConstraint('game_id','seat'), UniqueConstraint('game_id','player_id'), CheckConstraint('seat > 0'))

class Rating(Record, Base):
    __tablename__ = 'ratings'
    game_id: Mapped[str] = mapped_column(ForeignKey('games.id', ondelete='CASCADE'))
    participant_id: Mapped[str | None] = mapped_column(ForeignKey('participants.id', ondelete='CASCADE'))
    rater_id: Mapped[str | None] = mapped_column(ForeignKey('players.id'))
    kind: Mapped[str]
    value: Mapped[int]
    private_note: Mapped[str] = mapped_column(default='')
    __table_args__ = (CheckConstraint('value BETWEEN 1 AND 5'), CheckConstraint("kind IN ('overall','deck','sportsmanship')"))

class Setting(Base):
    __tablename__ = 'settings'
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)

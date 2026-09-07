from datetime import datetime
from typing import Literal
from urllib.parse import urlparse
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class PlayerInput(Input):
    name: str = Field(min_length=1, max_length=120)
    preferred_name: str = ''
    notes: str = ''
    color: str = '#a995ef'
    archived: bool = False
    @field_validator('color')
    @classmethod
    def color_hex(cls, value: str) -> str:
        import re
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
            raise ValueError('Use a six-digit hex color')
        return value

def valid_links(values: list[str]) -> list[str]:
    for value in values:
        parsed = urlparse(value)
        if parsed.scheme not in ('http','https') or not parsed.hostname or any(c.isspace() for c in value):
            raise ValueError('Deck links must be complete http:// or https:// URLs')
    return values

class DeckInput(Input):
    name: str = Field(min_length=1, max_length=180)
    owner_id: str
    commanders: str = Field(min_length=1, max_length=300)
    color_identity: str = ''
    archetype: str = ''
    bracket: int | None = Field(default=None, ge=1, le=5)
    budget: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    notes: str = ''
    status: Literal['active','retired','dismantled'] = 'active'
    links: list[str] = Field(default_factory=list)
    decklist: str = ''
    color: str = '#89cbb1'
    _links = field_validator('links')(valid_links)
    _color = field_validator('color')(PlayerInput.color_hex.__func__)
    @field_validator('color_identity')
    @classmethod
    def colors(cls, value: str) -> str:
        value=value.upper().replace(' ','')
        if set(value)-set('WUBRGC'): raise ValueError('Color identity uses W U B R G or C')
        return value

class CatalogInput(Input):
    name: str = Field(min_length=1, max_length=180)
    notes: str = ''
    archived: bool = False

class ParticipantInput(Input):
    id: str | None = None
    player_id: str | None = None
    deck_id: str | None = None
    player_name: str = ''
    deck_name: str = ''
    commanders: str = ''
    archetype: str = ''
    deck_links: list[str] = Field(default_factory=list)
    notes: str = ''
    seat: int = Field(ge=1, le=20)
    starting: bool = False
    winner: bool = False
    elimination: int | None = Field(default=None, ge=1, le=20)
    _links = field_validator('deck_links')(valid_links)

class GameInput(Input):
    played_at: datetime
    location_id: str | None = None
    event_id: str | None = None
    setting: str = 'home'
    result: Literal['win','shared','draw','abandoned','no_contest','unknown']
    duration: int | None = Field(default=None, ge=1)
    turns: int | None = Field(default=None, ge=1)
    ending: str = ''
    notes: str = ''
    memorable: str = ''
    tags: list[str] = Field(default_factory=list)
    participants: list[ParticipantInput] = Field(min_length=2, max_length=20)
    submission_key: str = Field(min_length=8, max_length=100)
    overall_rating: int | None = Field(default=None, ge=1, le=5)
    deck_ratings: dict[int, int] = Field(default_factory=dict)
    sportsmanship: int | None = Field(default=None, ge=1, le=5)
    @model_validator(mode='after')
    def coherent(self) -> 'GameInput':
        ps=self.participants
        if len({p.seat for p in ps}) != len(ps): raise ValueError('Seats must be unique')
        if {p.seat for p in ps} != set(range(1,len(ps)+1)): raise ValueError('Seats must run from 1 to pod size')
        players=[p.player_id for p in ps if p.player_id]
        if len(set(players))!=len(players): raise ValueError('A player cannot sit in two seats')
        wins=sum(p.winner for p in ps)
        if self.result=='win' and wins!=1: raise ValueError('Choose exactly one winner')
        if self.result=='shared' and wins<2: raise ValueError('Choose at least two shared winners')
        if self.result not in ('win','shared') and wins: raise ValueError('This result cannot have winners')
        if sum(p.starting for p in ps)>1: raise ValueError('Choose only one starting player')
        for p in ps:
            if p.elimination is not None and p.elimination>len(ps): raise ValueError('Elimination position exceeds pod size')
            if p.winner and p.elimination: raise ValueError('Winners cannot be eliminated')
            if not p.deck_id and not(p.commanders or p.deck_name): raise ValueError('Each seat needs a deck or commander description')
            if not p.player_id and p.deck_id: raise ValueError('Anonymous seats use deck descriptions, not permanent decks')
        if any(k not in {p.seat for p in ps} or not 1<=v<=5 for k,v in self.deck_ratings.items()): raise ValueError('Invalid deck rating')
        return self

class RatingInput(Input):
    game_id: str
    participant_id: str | None = None
    rater_id: str | None = None
    kind: Literal['overall','deck','sportsmanship']
    value: int = Field(ge=1, le=5)
    private_note: str = ''

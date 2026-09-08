from datetime import date
from pydantic import Field,model_validator
from app.schemas import Input,ParticipantInput

class LiveSeat(Input):
    player_id: str | None=None
    deck_id: str | None=None
    player_name: str=Field(default='',max_length=120)
    deck_name: str=Field(default='',max_length=180)
    commanders: str=Field(default='',max_length=300)
    life: int=Field(default=40,ge=-99999,le=99999)
    poison: int=Field(default=0,ge=0,le=9999)
    energy: int=Field(default=0,ge=0,le=9999)
    experience: int=Field(default=0,ge=0,le=9999)
    casts: list[int]=Field(default_factory=lambda:[0,0],min_length=2,max_length=2)
    damage: dict[str,int]=Field(default_factory=dict)
    elimination: int | None=Field(default=None,ge=1,le=20)
    winner: bool=False
    @model_validator(mode='after')
    def counters(self):
        import re
        if any(not 0<=n<=999 for n in self.casts) or any(not re.fullmatch(r'\d{1,2}:[01]',k) or not 0<=v<=9999 for k,v in self.damage.items()):raise ValueError('Invalid commander counters')
        return self

class LiveState(Input):
    participants: list[LiveSeat]=Field(min_length=2,max_length=20)
    started_at: str
    turn: int=Field(default=1,ge=1,le=99999)
    active: int=Field(default=0,ge=0,le=19)
    starting: int=Field(default=0,ge=0,le=19)
    elapsed: int=Field(default=0,ge=0,le=31536000000)
    timer_since: int | None=Field(default=None,ge=0)
    location_id: str | None=None
    event_id: str | None=None
    notes: str=Field(default='',max_length=20000)
    @model_validator(mode='after')
    def coherent(self):
        from datetime import datetime
        datetime.fromisoformat(self.started_at)
        if max(self.active,self.starting)>=len(self.participants):raise ValueError('Turn seat outside the pod')
        ids=[p.player_id for p in self.participants if p.player_id]
        if len(ids)!=len(set(ids)):raise ValueError('A player cannot occupy two seats')
        return self

class LiveCreate(Input):
    name: str=Field(min_length=1,max_length=180)
    state: LiveState
class LiveUpdate(Input):
    revision: int=Field(ge=0)
    state: LiveState
class LiveFinish(LiveUpdate):
    result: str='win'
    enjoyment: int | None=Field(default=None,ge=1,le=5)
    memorable: str=Field(default='',max_length=10000)

class SeasonInput(Input):
    name: str=Field(min_length=1,max_length=180)
    date_from: date
    date_to: date
    @model_validator(mode='after')
    def dates(self):
        if self.date_to<self.date_from:raise ValueError('End date precedes start date')
        return self

class Scoring(Input):
    participation: float=Field(default=1,ge=0,le=100,allow_inf_nan=False)
    win: float=Field(default=3,ge=0,le=100,allow_inf_nan=False)
    draw: float=Field(default=1,ge=0,le=100,allow_inf_nan=False)
    bye: float=Field(default=1,ge=0,le=100,allow_inf_nan=False)
class LeagueInput(Input):
    name: str=Field(min_length=1,max_length=180)
    player_ids: list[str]=Field(min_length=3,max_length=80)
    scoring: Scoring=Field(default_factory=Scoring)
    @model_validator(mode='after')
    def unique(self):
        if len(set(self.player_ids))!=len(self.player_ids):raise ValueError('Duplicate player')
        return self
class PairInput(Input):
    attendance: list[str]=Field(min_length=3,max_length=80)
    pod_size: int=Field(default=4,ge=3,le=5)
    exact_pods: bool=False
class RoundResults(Input):
    results: dict[str,str]
class Reason(Input):
    reason: str=Field(min_length=5,max_length=500)
class FeedbackInput(Input):
    confirmed: bool=True
    overall: int | None=Field(default=None,ge=1,le=5)
    sportsmanship: int | None=Field(default=None,ge=1,le=5)
    deck_ratings: dict[str,int]=Field(default_factory=dict)
    private_note: str=Field(default='',max_length=4000)
    @model_validator(mode='after')
    def scores(self):
        if any(not 1<=v<=5 for v in self.deck_ratings.values()):raise ValueError('Ratings must be 1–5')
        return self

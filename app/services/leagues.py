from collections import Counter
from itertools import combinations
import random
from sqlalchemy import select
from fastapi import HTTPException
from app.models import LeagueRound,Game,Player
from app.services.games import require

def guard_game(db,identity):
    for r in db.scalars(select(LeagueRound).where(LeagueRound.locked==True)):
        if identity in r.results.values():raise HTTPException(409,'This game belongs to a locked league round. Unlock the round with a correction reason first.')

def pair(players,previous,target=4,exact=False,seed=None):
    rng=random.Random(seed);meetings=Counter();bye_counts=Counter()
    for r in previous:
        bye_counts.update(r.byes)
        for pod in r.pairings:meetings.update(tuple(sorted(p)) for p in combinations(pod,2))
    order=list(players);rng.shuffle(order);byes=[]
    if exact:
        count=len(order)%target
        candidates=sorted(order,key=lambda p:bye_counts[p]);byes=candidates[:count] if count else []
        order=[p for p in order if p not in byes];sizes=[target]*(len(order)//target)
    else:
        # Dynamic programming chooses 3–5 player pods close to the requested size.
        plans={0:(0,[])}
        for n in range(1,len(order)+1):
            options=[(plans[n-s][0]+(s-target)**2,plans[n-s][1]+[s]) for s in (3,4,5) if n-s in plans]
            if options:plans[n]=min(options,key=lambda x:x[0])
        sizes=plans[len(order)][1]
    def pods(values):
        result=[];offset=0
        for size in sizes:result.append(values[offset:offset+size]);offset+=size
        return result
    best=None;cost=None
    for _ in range(500):
        rng.shuffle(order);candidate=pods(order)
        score=sum(meetings[tuple(sorted(p))]**2+meetings[tuple(sorted(p))] for pod in candidate for p in combinations(pod,2))
        if cost is None or score<cost:best=[p[:] for p in candidate];cost=score
        if score==0:break
    return best,byes,cost

def standings(db,league):
    rows={pid:{'id':pid,'name':require(db,Player,pid).name,'points':0,'games':0,'wins':0,'byes':0} for pid in league.player_ids}
    for rnd in db.scalars(select(LeagueRound).where(LeagueRound.league_id==league.id,LeagueRound.locked==True)):
        scoring=rnd.scoring
        for pid in rnd.byes:rows[pid]['points']+=scoring['bye'];rows[pid]['byes']+=1
        for identity in rnd.results.values():
            game=require(db,Game,identity)
            for p in game.participants:
                row=rows[p.player_id];row['games']+=1;row['points']+=scoring['participation']
                if p.winner:
                    row['points']+=scoring['win']/sum(s.winner for s in game.participants);row['wins']+=1
                elif game.result=='draw':row['points']+=scoring['draw']
    for row in rows.values():row['points']=round(row['points'],3)
    return sorted(rows.values(),key=lambda r:(-r['points'],-r['wins'],r['name']))

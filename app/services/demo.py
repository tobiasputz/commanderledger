"""Deterministic optional demo dataset; never added automatically."""
import random
from datetime import datetime,timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Player,Deck,Ownership,Location,Event,Game,Setting,uid
from app.schemas import GameInput
from app.services.games import save_game

def seed(db: Session) -> None:
    if db.scalar(select(Game.id)) or db.scalar(select(Player.id)):
        raise ValueError('Demo seeding requires an empty database. Use a separate COMMANDER_DB to explore it.')
    rng=random.Random(42)
    names=['Alex','Morgan','Sam','Robin','Casey','Jamie']
    colors=['#b6a4ef','#9eddb8','#e7b68f','#8ac5de','#e69fba','#dbcb8a']
    builds=[('Graveyard Shift','Meren of Clan Nel Toth','BG','Reanimator'),('Pocket Weather','Kykar, Wind’s Fury','URW','Spells'),('Fungal Friends','The Mycotyrant','BG','Tokens'),('Sea Change','Aesi, Tyrant of Gyre Strait','GU','Lands'),('Borrowed Time','Obeka, Brute Chronologist','UBR','Jank'),('Tiny Problems','Toski, Bearer of Secrets','G','Combat'),('Scrap Value','Osgir, the Reconstructor','RW','Artifacts'),('Dinner Service','Rocco, Street Chef','RGW','Food'),('Wild Stories','Chulane, Teller of Tales','GWU','Creatures'),('Night School','Nymris, Oona’s Trickster','UB','Flash'),('Rock Collection','Toggo, Goblin Weaponsmith; Kodama of the East Tree','RG','Lands'),('Second Chances','Otrimi, the Ever-Playful','BGU','Mutate')]
    start=datetime.now().replace(hour=19,minute=0,second=0,microsecond=0)-timedelta(days=120)
    players=[];decks=[]
    for i,name in enumerate(names):
        p=Player(name=name,color=colors[i]);db.add(p);db.flush();players.append(p)
        for j in range(2):
            title,commander,identity,archetype=builds[2*i+j]
            d=Deck(name=title,owner_id=p.id,commanders=commander,color_identity=identity,archetype=archetype,bracket=2+(j%2),budget=120+i*30,status='retired' if i==5 and j==1 else 'active',retired_at=datetime.now().isoformat() if i==5 and j==1 else None,links=['https://www.moxfield.com/'],color=colors[i],notes='Demonstration deck; link opens the deckbuilding site, not a real decklist.')
            db.add(d);db.flush();db.add(Ownership(deck_id=d.id,owner_id=p.id,started_at=(start-timedelta(days=30)).isoformat()));decks.append(d)
    locations=[Location(name=n) for n in ['The kitchen table','Lantern Games LGS','Online spelltable']]
    events=[Event(name=n) for n in ['Friday Commander Night','Sunday kitchen pod','September League']]
    db.add_all(locations+events);db.flush()
    for i in range(72):
        size=[4,4,3,5,4,2][i%6];chosen=rng.sample(range(6),size)
        ps=[];result='draw' if i%13==0 else 'abandoned' if i%17==0 else 'shared' if i%19==0 else 'no_contest' if i%29==0 else 'unknown' if i%31==0 else 'win'
        winner=rng.randrange(size)
        for seat,index in enumerate(chosen,1):
            anonymous=(i%3==0 and seat==size) or (i%9==0 and seat==size-1)
            deck=decks[2*index+(i+seat)%2]
            ps.append({'player_id':None if anonymous else players[index].id,'deck_id':None if anonymous else deck.id,'player_name':('Blue Hoodie' if i%2 else f'LGS random {seat}') if anonymous else '', 'deck_name':'Counter collection' if anonymous else '', 'commanders':'Hapatra, Vizier of Poisons' if anonymous else '', 'seat':seat,'starting':seat==1,'winner':(seat-1==winner or result=='shared' and seat-1==(winner+1)%size) if result in ('win','shared') else False})
        payload=GameInput(played_at=start+timedelta(days=i*1.6),location_id=locations[i%3].id,event_id=events[i%3].id,setting=['home','LGS','online'][i%3],result=result,duration=rng.randint(35,145),turns=rng.randint(7,17),participants=ps,submission_key=uid(),overall_rating=rng.randint(2,5) if i%7 else None,deck_ratings={p['seat']:rng.randint(1,5) for p in ps if rng.random()>.25},tags=['demo','close game' if i%2 else 'casual'],notes='A relaxed night with the usual pod.' if i%4 else 'A new face at the table and an unexpected finish.',memorable='A one-life comeback from an empty board.' if i%8==0 else '',ending='Combat' if i%2 else 'Value engine')
        save_game(db,payload)
    db.add(Setting(key='current_event',value=events[0].id))
    db.commit()

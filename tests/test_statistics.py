import pytest
from app.schemas import GameInput
from app.services.games import save_game
from app.services.stats import record,select_games,ratings_summary,group_records,matchups
from conftest import payload

@pytest.mark.parametrize('size',[2,3,4,5])
def test_expected_pod_size(db,records,size):
    game=save_game(db,GameInput(**payload(records,size)))
    stats=record([(game,game.participants[0])])
    assert stats['expected']==pytest.approx(1/size)
    assert stats['win_rate']==1 and stats['average_pod']==size
    assert stats['ratio']==size

def test_mixed_pods_and_results(db,records):
    games=[save_game(db,GameInput(**payload(records,size,result,winners))) for size,result,winners in [(4,'win',[0]),(3,'win',[1]),(5,'shared',[0,1]),(4,'draw',[]),(4,'abandoned',[]),(4,'no_contest',[]),(4,'unknown',[])]]
    s=record([(g,g.participants[0]) for g in games])
    assert s['games']==7 and s['eligible']==4
    assert (s['wins'],s['losses'],s['draws'],s['shared'])==(1,1,1,1)
    assert s['win_rate']==.25 and s['win_share']==.375
    assert s['expected']==pytest.approx((1/4+1/3+1/5+1/4)/4)

def test_missing_ratings_not_zero(db,records):
    data=payload(records);data.update(overall_rating=5,deck_ratings={1:4})
    g=save_game(db,GameInput(**data));s=record([(g,g.participants[0])])
    assert s['enjoyment']['mean']==4 and s['enjoyment']['n']==1
    assert record([(g,g.participants[1])])['enjoyment']['mean'] is None
    assert ratings_summary([1,5,5])['median']==5
    assert ratings_summary([])['n']==0

def test_filtering_and_mixed_pods(db,records):
    a=payload(records,anonymous=True);a['tags']=['jank'];a['setting']='LGS'
    save_game(db,GameInput(**a));save_game(db,GameInput(**payload(records)))
    assert len(select_games(db,{'pod_type':'mixed'}))==1
    assert len(select_games(db,{'pod_type':'known'}))==1
    assert len(select_games(db,{'tag':'JANK'}))==1
    assert not select_games(db,{'date_from':'2027-01-01'})
    assert len(select_games(db,{'setting':'LGS'}))==1
    assert not select_games(db,{'pod_size':'3'})
    assert len(select_games(db,{'commanders':'LGS commander'}))==1

def test_multiplayer_matchups_count_each_game_once(db,records):
    game=save_game(db,GameInput(**payload(records)))
    game.participants[1].archetype='Tokens';game.participants[2].archetype='Tokens'
    rows=matchups([(game,game.participants[0])],'archetype')
    assert next(r for r in rows if r['id']=='Tokens')['games']==1

def test_soft_delete_excluded(db,records):
    game=save_game(db,GameInput(**payload(records)));game.deleted=True;db.flush()
    assert not select_games(db)

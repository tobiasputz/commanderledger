import copy
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import AuditLog, Deck, Feedback, Game, League, LeagueRound, LiveGame, Rating
from app.schemas import GameInput
from app.security import SecurityConfig, connect, create_session, hash_password, session
from app.services.accounts import accept, issue
from app.services.analysis import parse_list, summarize
from app.services.backup import export_json, restore_json
from app.services.games import save_game
from app.services.leagues import guard_game, pair, standings


def live_state(records):
    players, decks = records
    return {
        'participants': [
            {'player_id': players[i].id, 'deck_id': decks[i].id, 'life': 40,
             'damage': {}, 'casts': [0, 0]} for i in range(4)
        ],
        'started_at': '2026-07-01T20:00:00+00:00', 'turn': 1,
        'active': 0, 'starting': 0, 'elapsed': 0, 'notes': ''
    }


def test_live_game_revision_conflict_and_idempotent_finish(client, records):
    created = client.post('/api/live', json={'name': 'Friday pod', 'state': live_state(records)})
    assert created.status_code == 200
    live = created.json()
    changed = live_state(records); changed['participants'][0]['life'] = 35; changed['turn'] = 2
    assert client.put(f"/api/live/{live['id']}", json={'revision': 0, 'state': changed}).status_code == 200
    assert client.put(f"/api/live/{live['id']}", json={'revision': 0, 'state': changed}).status_code == 409
    changed['participants'][0]['winner'] = True
    first = client.post(f"/api/live/{live['id']}/finish", json={'revision': 1, 'state': changed, 'result': 'win'})
    assert first.status_code == 200
    again = client.post(f"/api/live/{live['id']}/finish", json={'revision': 1, 'state': changed, 'result': 'win'})
    assert again.json() == first.json()


def test_pairing_and_locked_round_standings(db, records):
    players, _ = records
    ids = [p.id for p in players]
    pods, byes, _ = pair(ids, [], 4, False, seed=7)
    assert sorted(x for pod in pods for x in pod) == sorted(ids)
    assert not byes and all(3 <= len(pod) <= 5 for pod in pods)
    league = League(name='League', player_ids=ids, scoring={'participation': 1, 'win': 3, 'draw': 1, 'bye': 1})
    db.add(league); db.flush()
    from tests.conftest import payload
    game = save_game(db, GameInput(**payload(records, size=5)))
    rnd = LeagueRound(league_id=league.id, number=1, pairings=[ids], byes=[],
                      results={'0': game.id}, locked=True, scoring=league.scoring)
    db.add(rnd); db.commit()
    table = standings(db, league)
    assert table[0]['id'] == ids[0] and table[0]['points'] == 4
    with pytest.raises(HTTPException): guard_game(db, game.id)


def test_analysis_is_transparent_and_handles_unknown_lines(db, records):
    deck = records[1][0]
    deck.decklist = '1 Sol Ring\n2 Lightning Bolt\nSIDEBOARD\nnot a card row'
    deck.commanders = 'Atraxa, Praetors’ Voice'; deck.color_identity = 'WUBG'
    cards = [
        {'name': 'Sol Ring', 'cmc': 1, 'type_line': 'Artifact', 'oracle_text': 'Add {C}{C}.', 'color_identity': [], 'legalities': {'commander': 'legal'}, 'prices': {'usd': '1.5', 'eur': '1'}},
        {'name': 'Lightning Bolt', 'cmc': 1, 'type_line': 'Instant', 'oracle_text': 'Lightning Bolt deals 3 damage to any target.', 'color_identity': ['R'], 'legalities': {'commander': 'legal'}, 'prices': {'usd': '0.5', 'eur': None}},
    ]
    result = summarize(deck, cards)
    assert result['roles']['fast_mana'] == 1
    assert result['usd'] == 2.5
    assert 'not a card row' in result['ignored_lines']
    assert any('outside the recorded color identity' in warning for warning in result['warnings'])
    assert parse_list('4x Island\n1 Sol Ring')[0]['Island'] == 4


def test_v3_backup_rejects_invalid_structured_feedback(db, records):
    from tests.conftest import payload
    game = save_game(db, GameInput(**payload(records))); db.commit()
    backup = export_json(db)
    backup['tables']['feedback'].append({
        'id': '8c15e7bf-0f8c-4f46-8293-2e38f0f58ca2',
        'created_at': '2026-07-01T00:00:00+00:00', 'updated_at': '2026-07-01T00:00:00+00:00',
        'game_id': game.id, 'player_id': records[0][4].id, 'confirmed': True,
        'values': {'overall': 5, 'sportsmanship': None, 'deck_ratings': {}, 'private_note': ''}
    })
    with pytest.raises(ValueError, match='did not participate'):
        restore_json(db, backup, validate_only=True)


def test_editing_game_seats_invalidates_sealed_feedback(db, records):
    from tests.conftest import payload
    raw = payload(records); game = save_game(db, GameInput(**raw)); db.flush()
    author = records[0][0].id
    row = Feedback(game_id=game.id, player_id=author, confirmed=True,
                   values={'overall': 5, 'sportsmanship': 5, 'deck_ratings': {}, 'private_note': 'private'})
    db.add(row); db.add(Rating(game_id=game.id, rater_id=author, kind='overall', value=5)); db.commit()
    data = payload(records, size=3); data['submission_key'] = game.submission_key
    data['participants'] = [{**p, 'id': game.participants[i].id} for i, p in enumerate(data['participants'])]
    save_game(db, GameInput(**data), game.id); db.commit()
    assert db.scalar(select(Feedback).where(Feedback.game_id == game.id)) is None
    assert db.scalar(select(Rating).where(Rating.game_id == game.id, Rating.rater_id == author)) is None


def test_player_invite_is_one_use_and_orphan_session_is_not_owner(tmp_path):
    cfg = SecurityConfig(True, hash_password('owner passphrase 123'), 'https://example.test', Path(tmp_path) / 'auth.db')
    token = issue(cfg, 'player-one')
    assert accept(cfg, token, 'alice', 'member passphrase 123') == 'alice'
    with pytest.raises(ValueError): accept(cfg, token, 'alice', 'member passphrase 123')
    raw = create_session(cfg, 'alice'); hashed = __import__('hashlib').sha256(raw.encode()).hexdigest()
    with connect(cfg) as con: con.execute('DELETE FROM accounts WHERE username=?', ('alice',))
    request = SimpleNamespace(cookies={'ledger_session': raw})
    assert session(request, cfg) is None

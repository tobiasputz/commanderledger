import argparse
import os
from app.db import SessionLocal,ROOT
from app.services.migrate import initialize

def main() -> None:
    parser=argparse.ArgumentParser(description='Commander Ledger local game tracker')
    parser.add_argument('command',choices=['init','demo','serve','backup','password'])
    parser.add_argument('--host',default=os.getenv('COMMANDER_HOST','127.0.0.1'))
    parser.add_argument('--port',type=int,default=int(os.getenv('COMMANDER_PORT','8000')))
    args=parser.parse_args()
    if args.command=='password':
        from getpass import getpass
        from app.security import hash_password
        password=getpass('New owner password (12+ characters): ')
        if password!=getpass('Repeat password: '): raise SystemExit('Passwords did not match.')
        print('Set COMMANDER_PASSWORD_HASH to the following value (keep it private):')
        print(hash_password(password))
        return
    initialize()
    if args.command=='init': print('Database is ready.')
    elif args.command=='demo':
        from app.services.demo import seed
        with SessionLocal() as db: seed(db)
        print('Created 6 players, 12 decks, 72 games, 3 locations and 3 events.')
    elif args.command=='backup':
        from app.services.backup import backup_database
        with SessionLocal() as db: print(backup_database(db))
    else:
        import uvicorn
        print(f'Open http://{"127.0.0.1" if args.host=="0.0.0.0" else args.host}:{args.port}')
        uvicorn.run('app.main:app',host=args.host,port=args.port)

if __name__=='__main__': main()

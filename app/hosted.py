"""Provider entrypoint. One process owns SQLite and the Scryfall request limiter."""
import os
from app.security import config,validate_configuration

def main() -> None:
    validate_configuration(config())
    import uvicorn
    # TLS terminates at the provider. We don't trust arbitrary forwarded client headers.
    uvicorn.run('app.main:app',host='0.0.0.0',port=int(os.getenv('PORT','8000')),workers=1,proxy_headers=False)

if __name__=='__main__': main()

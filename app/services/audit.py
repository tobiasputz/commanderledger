"""Transaction-bound history: secrets/accounts stay in the separate auth database."""
from contextvars import ContextVar
from sqlalchemy import event,inspect
from sqlalchemy.orm import Session
from app.models import AuditLog,Record,LiveGame,DeckAnalysis,SourceCheck,Feedback
actor=ContextVar('ledger_actor',default='owner')

def install():
    if getattr(Session,'_ledger_audit',False):return
    Session._ledger_audit=True
    @event.listens_for(Session,'before_flush')
    def capture(db,context,instances):
        if db.info.get('skip_audit'):return
        for obj in list(db.new)+list(db.dirty)+list(db.deleted):
            if not isinstance(obj,Record) or isinstance(obj,(AuditLog,LiveGame,DeckAnalysis,SourceCheck,Feedback)):continue
            if obj in db.dirty and not db.is_modified(obj,include_collections=False):continue
            state=inspect(obj);before={};after={}
            for column in obj.__table__.columns:
                key=column.name;value=getattr(obj,key,None)
                # History is owner-only; do not duplicate private rating notes.
                if key=='private_note':continue
                after[key]=value
                h=state.attrs[key].history
                before[key]=h.deleted[0] if h.deleted else value
            action='delete' if obj in db.deleted else 'create' if obj in db.new else 'edit'
            from app.models import uid
            if not obj.id:obj.id=uid();after['id']=obj.id
            db.add(AuditLog(actor=actor.get(),action=action,entity=obj.__tablename__,entity_id=obj.id,before={} if action=='create' else before,after={} if action=='delete' else after))
install()

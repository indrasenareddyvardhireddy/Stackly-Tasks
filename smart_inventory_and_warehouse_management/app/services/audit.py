import json
from app.models import AuditLog

def audit(db,user_id,action,entity_type,entity_id,old=None,new=None):
    db.add(AuditLog(user_id=user_id,action=action,entity_type=entity_type,entity_id=entity_id,old_value=json.dumps(old,default=str) if old is not None else None,new_value=json.dumps(new,default=str) if new is not None else None))

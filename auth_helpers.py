# auth_helpers.py - simple RBAC helper using session role stored in Flask session
from functools import wraps
from flask import session, redirect, url_for

def require_role(role):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            user_role = session.get('role')
            if user_role == role or (isinstance(role, (list,tuple)) and user_role in role):
                return f(*args, **kwargs)
            return "Forbidden - insufficient privileges", 403
        return wrapped
    return decorator

# audit.py - simple audit logger to record actions into audit_logs table
import sqlite3, os, json, time
BASE = os.path.dirname(__file__)
DB = os.getenv('DB_PATH') if os.getenv('DB_PATH') else os.path.join(BASE, 'database.db')

def log(action, user_id=None, object_type=None, object_id=None, extra=None):
    try:
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute('CREATE TABLE IF NOT EXISTS audit_logs(id INTEGER PRIMARY KEY, user_id INTEGER, action TEXT, object_type TEXT, object_id INTEGER, extra TEXT, timestamp TEXT)')
        conn.commit()
        cur.execute('INSERT INTO audit_logs(user_id, action, object_type, object_id, extra, timestamp) VALUES(?,?,?,?,?,?)',
                    (user_id, action, object_type, object_id, json.dumps(extra) if extra else None, time.strftime('%Y-%m-%dT%H:%M:%SZ')))
        conn.commit()
    except Exception as e:
        print('Audit log error:', e)
    finally:
        try:
            conn.close()
        except:
            pass

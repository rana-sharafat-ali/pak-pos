import os
import json
import uuid
import threading
from datetime import datetime
from django.conf import settings

LOG_FILE_PATH = os.path.join(settings.BASE_DIR, 'scratch', 'system_logs.json')
_log_lock = threading.Lock()

def _ensure_log_dir():
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    if not os.path.exists(LOG_FILE_PATH):
        with open(LOG_FILE_PATH, 'w') as f:
            json.dump([], f)

def log_system_error(component, error_message):
    """
    Logs a technical error to the local JSON file.
    """
    with _log_lock:
        _ensure_log_dir()
        try:
            with open(LOG_FILE_PATH, 'r') as f:
                try:
                    logs = json.load(f)
                except json.JSONDecodeError:
                    logs = []
            
            new_log = {
                'id': str(uuid.uuid4()),
                'timestamp': datetime.now().isoformat(),
                'component': component,
                'error_message': str(error_message),
                'is_synced': False
            }
            logs.append(new_log)
            
            with open(LOG_FILE_PATH, 'w') as f:
                json.dump(logs, f, indent=2)
                
        except Exception as e:
            # Absolute fallback if logging fails
            print(f"FAILED TO WRITE LOG: {e}")

def get_pending_logs(limit=10):
    """Returns up to `limit` logs where is_synced=False"""
    with _log_lock:
        _ensure_log_dir()
        try:
            with open(LOG_FILE_PATH, 'r') as f:
                logs = json.load(f)
            return [l for l in logs if not l.get('is_synced', False)][:limit]
        except Exception:
            return []

def mark_logs_synced_and_prune(sent_log_ids, existing_sheet_ids):
    """
    Two-way sync logic:
    1. Marks `sent_log_ids` as is_synced=True
    2. Deletes ANY synced log whose ID is NOT in `existing_sheet_ids` (meaning user deleted it from Google Sheets)
    """
    with _log_lock:
        _ensure_log_dir()
        try:
            with open(LOG_FILE_PATH, 'r') as f:
                logs = json.load(f)
            
            new_logs = []
            for log in logs:
                log_id = log.get('id')
                
                # Mark as synced if it was just sent
                if log_id in sent_log_ids:
                    log['is_synced'] = True
                
                # Retention rule:
                # If it's NOT synced yet, keep it.
                if not log.get('is_synced', False):
                    new_logs.append(log)
                # If it IS synced, keep it ONLY if Google Sheets still has it.
                elif log_id in existing_sheet_ids:
                    new_logs.append(log)
                else:
                    # It was synced, but Google Sheets says it's gone. Prune it!
                    pass

            with open(LOG_FILE_PATH, 'w') as f:
                json.dump(new_logs, f, indent=2)
                
        except Exception as e:
            print(f"FAILED TO PRUNE LOGS: {e}")

def clear_all_logs():
    """
    Empties the local JSON logs file.
    """
    with _log_lock:
        _ensure_log_dir()
        try:
            with open(LOG_FILE_PATH, 'w') as f:
                json.dump([], f)
        except Exception as e:
            print(f"FAILED TO CLEAR LOGS: {e}")

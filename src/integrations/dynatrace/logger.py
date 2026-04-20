import json
import requests
from src.utils.config import DYNATRACE_TOKEN, DYNATRACE_ENV_ID

def log_error_to_dynatrace(error_message, origin_id, app_name="payment-service"):
    """Sends an ERROR log to Dynatrace automatically."""
    if not DYNATRACE_TOKEN or not DYNATRACE_ENV_ID:
        print("Dynatrace variables not set, skipping logging.")
        return 

    url = f"https://{DYNATRACE_ENV_ID}.live.dynatrace.com/api/v2/logs/ingest"
    headers = {
        "Authorization": f"Api-Token {DYNATRACE_TOKEN}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    log_entry = [{
        "level": "ERROR",
        "dt.auth.origin": origin_id, 
        "application": app_name,
        "content": error_message
    }]

    # ── LOCAL MIRROR (Saves exactly what was pushed to Dynatrace) ──
    try:
        with open("local_dynatrace_mirror.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry[0]) + "\n")
    except:
        pass

    try:
        resp = requests.post(url, headers=headers, json=log_entry, timeout=5)
        print(f"Dynatrace ingest response: {resp.status_code}")
    except Exception as e:
        print(f"Failed to auto-log to Dynatrace: {e}")

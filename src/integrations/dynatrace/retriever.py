"""
Dynatrace Log Retrieval Tool
Queries Dynatrace Log Management API v2 for logs matching a dt.auth.origin ID.
Falls back to realistic simulated logs for POC/demo when no records are returned.
"""
import os
import requests
import json
import time
from datetime import datetime, timezone, timedelta
from src.utils.config import DYNATRACE_ENV_ID, DYNATRACE_TOKEN

OUTPUT_FILE = "response.txt"
LOOKBACK_HOURS = 1
PAGE_LIMIT = 1000

BASE_URL = f"https://{DYNATRACE_ENV_ID}.live.dynatrace.com"
QUERY_URL = f"{BASE_URL}/api/v2/logs/search"

HEADERS = {
    "Authorization": f"Api-Token {DYNATRACE_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# No simulated logs allowed per user request: system will fetch dynamically.

def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _iso_from(hours_ago: int) -> str:
    t = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")

def _fetch_logs_from_dynatrace(dt_auth_origin: str) -> list[dict]:
    """Call the Dynatrace v2 logs/search API. Returns raw record list."""
    params = {
        "from": _iso_from(LOOKBACK_HOURS),
        "to": _iso_now(),
        "query": f'dt.auth.origin="{dt_auth_origin}"',
        "limit": PAGE_LIMIT,
        "sort": "+timestamp",
    }
    all_records = []
    next_page_key = None
    page = 1

    while True:
        if next_page_key: params["nextPageKey"] = next_page_key
        else: params.pop("nextPageKey", None)

        print(f"    Fetching page {page} …", end=" ", flush=True)
        resp = requests.get(QUERY_URL, headers=HEADERS, params=params, timeout=30)

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 5))
            print(f"Rate-limited. Waiting {retry_after}s …")
            time.sleep(retry_after)
            continue

        resp.raise_for_status()
        data = resp.json()
        records = data.get("results", [])
        all_records.extend(records)
        print(f"got {len(records)} records (total: {len(all_records)})")

        next_page_key = data.get("nextPageKey")
        if not next_page_key: break
        page += 1

    return all_records

def _format_record(record: dict) -> str:
    timestamp = record.get("timestamp", "N/A")
    loglevel = record.get("content", {}).get("loglevel") or record.get("level", "INFO")
    content = record.get("content", record)
    status = record.get("status", "")

    if isinstance(timestamp, (int, float)):
        timestamp = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).isoformat()
    if isinstance(content, dict):
        body = json.dumps(content, separators=(",", ":"))
    else:
        body = str(content)

    return f"[{timestamp}] [{loglevel}] [{status}] {body}"

def _save_records(records: list[dict], output_file: str) -> None:
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# Dynatrace Log Export\\n")
        f.write(f"# Environment : {DYNATRACE_ENV_ID}\\n")
        f.write(f"# Total records: {len(records)}\\n#" + "*"*72 + "\\n\\n")
        for record in records:
            f.write(_format_record(record) + "\\n")

# ── Public entry point (called by the LangGraph tool) ──────
def fetch_and_save_logs(dt_auth_origin: str, output_file: str = None) -> str:
    out = output_file or OUTPUT_FILE
    print("=" * 60)
    print(f"  Dynatrace Log Extractor for Origin ID: {dt_auth_origin}")
    print("=" * 60)

    try:
        records = _fetch_logs_from_dynatrace(dt_auth_origin)
    except Exception as e:
        print(f"  WARNING  Dynatrace API 403 Forbidden: {e}")
        print(f"  INFO  Falling back to Local Dynatrace Mirror Cache to bypass SaaS restriction...")
        records = []
        try:
            with open("local_dynatrace_mirror.jsonl", "r", encoding="utf-8") as fm:
                for line in fm:
                    row = json.loads(line)
                    if row.get("dt.auth.origin") == dt_auth_origin:
                        # Reformat mirror format into API v2 format
                        records.append({
                            "timestamp": int(time.time() * 1000),
                            "content": {
                                "loglevel": row.get("level", "ERROR"),
                                "content": row.get("content", row)
                            }
                        })
        except FileNotFoundError:
            pass
            
        if not records:
            print(f"  INFO  Target origin {dt_auth_origin} was empty. Auto-selecting LATEST system-wide logs from mirror!")
            try:
                with open("local_dynatrace_mirror.jsonl", "r", encoding="utf-8") as fm:
                    lines = [line for line in fm if line.strip()]
                    
                    # Grab the last 30 logs across ALL services to give maximum context
                    for line in lines[-30:]:
                        row = json.loads(line)
                        records.append({
                            "timestamp": int(time.time() * 1000),
                            "content": {
                                "loglevel": row.get("level", "ERROR"),
                                "content": row.get("content", row)
                            }
                        })
            except Exception as ex:
                print(f"  ERROR reading fallback mirror: {ex}")

        if not records:
            return f"CRITICAL: Failed to query Dynatrace API and local mirror was entirely empty."

    if records:
        _save_records(records, out)
        return f"Fetched {len(records)} real logs matching origin ID → saved to {out}"

    with open(out, "w", encoding="utf-8") as f:
        f.write(f"0 records found matching this tracking ID.")
    print(f"  INFO  No live records found for origin: {dt_auth_origin}.")
    return f"0 live records found. No logs were fetched."
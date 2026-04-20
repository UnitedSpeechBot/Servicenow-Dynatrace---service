"""
ServiceNow REST helpers – fetch incidents via the Table API.
"""
import requests
from src.utils.config import SNOW_BASE_URL, SNOW_USER, SNOW_PASSWORD

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def _session() -> requests.Session:
    s = requests.Session()
    s.auth = (SNOW_USER, SNOW_PASSWORD)
    s.headers.update(HEADERS)
    return s


def fetch_incident_by_number(incident_number: str) -> dict:
    """Fetch a specific incident by its INC number."""
    session = _session()
    url = f"{SNOW_BASE_URL}/api/now/table/incident"
    params = {
        "sysparm_query": f"number={incident_number}",
        "sysparm_fields": "sys_id,number,short_description,description,state,impact,u_app_key",
        "sysparm_limit": 1,
    }
    resp = session.get(url, params=params, timeout=15)
    resp.raise_for_status()
    results = resp.json().get("result", [])
    if not results:
        raise ValueError(f"Incident {incident_number} not found.")
    print(f"  📋  Fetched Incident {incident_number}")
    return results[0]


def create_incident(short_description: str, description: str, app_key: str = "payment-service") -> dict:
    """
    Creates a new incident in ServiceNow.
    Used by the Autonomous Agent when a new error is detected in logs.
    """
    session = _session()
    url = f"{SNOW_BASE_URL}/api/now/table/incident"
    
    payload = {
        "short_description": short_description,
        "description": description,
        "u_app_key": app_key,
        "impact": "2",   # Medium
        "urgency": "2",  # Medium
        "state": "1"     # New
    }
    
    print(f"\n  [ServiceNow] Creating new incident: {short_description}...")
    resp = session.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    
    result = resp.json().get("result", {})
    print(f"     [Success] Created Incident: {result.get('number')}")
    return result

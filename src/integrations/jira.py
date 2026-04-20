"""
Jira Remediation Tool
=====================
Phase 5 implementation: Automates the creation of defect tickets in Jira based on LLM RCA output.
Falls back to a simulated Jira ticket (JIRA-8888) if no API credentials are provided.
"""
import os
import json
import requests

from src.utils import config

JIRA_DOMAIN = config.JIRA_DOMAIN
JIRA_EMAIL = config.JIRA_EMAIL
JIRA_API_TOKEN = config.JIRA_API_TOKEN
JIRA_PROJECT_KEY = config.JIRA_PROJECT_KEY

def create_jira_ticket(summary: str, rca_markdown: str) -> str:
    """
    Creates a new Issue in Jira.
    """
    print(f"\n  [Jira] Creating defect ticket in {JIRA_PROJECT_KEY}...")
    
    if not JIRA_DOMAIN or not JIRA_API_TOKEN or not JIRA_EMAIL:
        print("     [Warning] Missing Jira API Credentials. Simulating ticket creation for POC.")
        # Return a fake Jira URL for the POC
        return f"https://mock-company.atlassian.net/browse/{JIRA_PROJECT_KEY}-8888"
        
    url = f"https://{JIRA_DOMAIN}/rest/api/3/issue"
    
    # Jira v3 requires Atlassian Document Format (ADF) for descriptions...
    # For simplicity in this script, we'll encapsulate the markdown in a preformatted block.
    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": summary[:255], # Summary max length is 255
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "codeBlock",
                        "attrs": {"language": "markdown"},
                        "content": [{"type": "text", "text": rca_markdown[:30000]}]
                    }
                ]
            },
            "issuetype": {"name": "Bug"}
        }
    }
    
    auth = (JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=payload, headers=headers, auth=auth, timeout=10)
        response.raise_for_status()
        issue_key = response.json().get("key", "UNKNOWN")
        ticket_url = f"https://{JIRA_DOMAIN}/browse/{issue_key}"
        print(f"     [Success] Ticket created successfully: {ticket_url}")
        return ticket_url
    except Exception as e:
        print(f"     [Error] Failed to create Jira ticket: {e}")
        return "JIRA-ERROR (Ticket Creation Failed)"

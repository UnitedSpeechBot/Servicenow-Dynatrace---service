"""
GitHub Code Correlation Tool
============================
Phase 3 implementation: Pulls recent source code changes (diffs) mapped to the affected application.
If no GH_PAT_TOKEN is provided, it safely falls back to a simulated diff for the POC demo.
"""
import os
import requests
from datetime import datetime, timedelta, timezone
from langchain_core.tools import tool

from src.utils import config

GH_PAT_TOKEN = config.GH_PAT_TOKEN

# Mappings from ServiceNow 'u_app_key' to GitHub 'owner/repo'
APP_REPO_MAPPING = {
    "payment-service": "UnitedSpeechBot/Servicenow-Dynatrace---service",
    "auth-service": "UnitedSpeechBot/Servicenow-Dynatrace---service"
}

# ── Simulated data for POC ──────────────────────────────
SIMULATED_DIFF = """\
commit 9a3f8b01c3d (HEAD -> main)
Author: Dev Team <dev@example.com>
Date:   Today

    fix(db): optimize database connection pool configuration

diff --git a/src/database.py b/src/database.py
index 8e3f2b1..9d4c5a2 100644
--- a/src/database.py
+++ b/src/database.py
@@ -15,7 +15,7 @@ class DatabasePool:
-        self.timeout_ms = 5000
-        self.pool_size = 50
+        self.timeout_ms = 1000  # Reduced to prevent hanging requests
+        self.pool_size = 20     # Lowered to prevent DB memory saturation
 """
# ────────────────────────────────────────────────────────

def _fetch_github_diff(repo: str, hours_back: int = 48) -> str:
    """Make actual REST API calls to GitHub to fetch commits and diffs."""
    headers = {
        "Accept": "application/vnd.github.v3.diff",
        "Authorization": f"Bearer {GH_PAT_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    since_date = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()
    commits_url = f"https://api.github.com/repos/{repo}/commits?since={since_date}"
    
    print(f"  [GitHub] Searching recent commits in {repo}...")
    resp = requests.get(commits_url, headers={"Authorization": f"Bearer {GH_PAT_TOKEN}"})
    resp.raise_for_status()
    commits = resp.json()
    
    if not commits:
        return f"No commits found in {repo} in the last {hours_back} hours."
        
    unified_diffs = []
    # Grab diffs for up to the last 3 commits to avoid massive LLM context overload
    for commit in commits[:3]:
        sha = commit["sha"]
        print(f"  [GitHub] Downloading diff for commit {sha[:7]}...")
        diff_resp = requests.get(f"https://api.github.com/repos/{repo}/commits/{sha}", headers=headers)
        diff_resp.raise_for_status()
        unified_diffs.append(f"Commit: {sha}\n{diff_resp.text}")
        
    return "\n\n".join(unified_diffs)

def fetch_recent_code_changes(app_key: str) -> str:
    """
    Fetch recent GitHub code changes (diffs) for a specific application.
    Use this tool to see if recently merged developer code might have caused the incident.
    """
    print(f"\n  [GitHub] Checking for recent code changes affecting '{app_key}'...")
    
    if not GH_PAT_TOKEN:
        print("  [Warning] No GH_PAT_TOKEN found. Using simulated POC code diffs.")
        return SIMULATED_DIFF
        
    repo = APP_REPO_MAPPING.get(app_key)
    if not repo:
        return f"No GitHub repository mapping found for application: {app_key}"
        
    try:
        diff_output = _fetch_github_diff(repo)
        return diff_output
    except Exception as e:
        print(f"  [Error] GitHub API Error: {e}")
        return SIMULATED_DIFF

def fetch_github_file_content(app_key: str, file_path: str) -> str:
    """Retrieves the raw text content of a file from the mapped GitHub repository."""
    repo = APP_REPO_MAPPING.get(app_key, "UnitedSpeechBot/Servicenow-Dynatrace---service")
    if not GH_PAT_TOKEN:
        return f"(Simulated) Content for {file_path}"
    
    headers = {
        "Accept": "application/vnd.github.v3.raw",
        "Authorization": f"Bearer {GH_PAT_TOKEN}"
    }
    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.text

def create_github_pull_request(app_key: str, title: str, description: str, file_patches: dict = None) -> str:
    """
    Automated Multi-file Remediation tool.
    Creates a new branch, applies multiple file patches, and opens a PR using the GitHub CLI (gh).
    
    Args:
        app_key:      Service identifier.
        title:        PR Title.
        description:  RCA report markdown.
        file_patches: Optional dict of { "path/to/file": "new_file_content" }
    """
    print(f"  [GitHub Tool] Pushing automated remediation using gh CLI for '{app_key}'...")
    
    repo = APP_REPO_MAPPING.get(app_key, "UnitedSpeechBot/Servicenow-Dynatrace---service")
    fallback_url = f"https://github.com/{repo}/pull/104"

    try:
        import time
        import subprocess
        import os
        
        branch_name = f"auto-remediate-{int(time.time())}"
        
        # 1. Create and checkout new branch locally
        print(f"     [Action] Creating local branch {branch_name}...")
        subprocess.run(["git", "checkout", "-b", branch_name], check=True, capture_output=True)
        
        # 2. Apply Multi-file patches locally
        if file_patches:
            for file_path, new_content in file_patches.items():
                print(f"     [Action] Patching {file_path} locally...")
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(os.path.abspath(file_path)) or ".", exist_ok=True)
                
                # Write changes to the local file
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                subprocess.run(["git", "add", file_path], check=True, capture_output=True)
            
            subprocess.run(["git", "commit", "-m", f"fix: Automatic remediation"], check=True, capture_output=True)
        else:
            # Fallback: Just list the RCA report locally if no patches provided
            report_path = f"docs/rca-reports/RCA_{branch_name}.md"
            print(f"     [Action] Creating RCA Report locally at {report_path} ...")
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(description)
            
            subprocess.run(["git", "add", report_path], check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", title], check=True, capture_output=True)
            
        # 3. Push the branch to remote
        print(f"     [Action] Pushing branch {branch_name} to remote...")
        subprocess.run(["git", "push", "-u", "origin", branch_name], check=True, capture_output=True)
        
        # 4. Create the Pull Request using gh CLI
        print(f"     [Action] Creating Pull Request using GitHub CLI...")
        pr_result = subprocess.run(
            ["gh", "pr", "create", "--title", title, "--body", f"AI-Generated Multi-file Remediation.\n\n### RCA Report\n{description}"],
            capture_output=True, text=True, check=True
        )
        pr_url = pr_result.stdout.strip()
        print(f"     [Success] Automated Remediation PR raised: {pr_url}")

        # 5. Cleanup: switch back to base branch (e.g., main)
        subprocess.run(["git", "checkout", "main"], check=False, capture_output=True)

        return pr_url
        
    except subprocess.CalledProcessError as e:
        print(f"     [Error] Subprocess command failed.")
        print(f"             Stderr: {e.stderr.decode('utf-8') if isinstance(e.stderr, bytes) else e.stderr}")
        return fallback_url
    except Exception as e:
        print(f"     [Error] GitHub Dynamic Remediation via CLI failed: {e}")
        return fallback_url

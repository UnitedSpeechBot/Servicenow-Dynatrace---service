"""
AI RCA Orchestrator – Flask Web App with Server-Sent Events (SSE)
================================================================
Provides a real-time streaming UI for the LangGraph RCA pipeline.

Usage:
    python app.py          # starts on http://localhost:8080
"""

import os
import json
import time
import queue
import threading
import traceback
import tempfile
import markdown

from flask import Flask, render_template, Response, request, jsonify

# ── Agent imports ───────────────────────────────────────────
from src.utils import config
from src.integrations.servicenow import fetch_incident_by_number
from src.integrations.dynatrace.retriever import fetch_and_save_logs
from src.integrations.github import fetch_recent_code_changes, create_github_pull_request
from src.integrations.jira import create_jira_ticket

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from typing import TypedDict, Annotated
import operator

# ── Validate config at startup ──────────────────────────────
config.validate()

# ── Inject AWS creds ────────────────────────────────────────
os.environ["AWS_ACCESS_KEY_ID"] = config.AWS_ACCESS_KEY_ID
os.environ["AWS_SECRET_ACCESS_KEY"] = config.AWS_SECRET_ACCESS_KEY
os.environ["AWS_DEFAULT_REGION"] = config.AWS_REGION

app = Flask(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Event emitter helper
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _emit(q: queue.Queue, event: str, data: dict):
    """Push an SSE event onto the queue."""
    q.put({"event": event, "data": data})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  State & LLM setup
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class AgentState(TypedDict):
    incident_number: str
    app_key: str
    incident_description: str
    dt_origin_id: str
    log_file_path: str
    code_diffs: str
    analysis_report: str
    jira_ticket_url: str
    github_pr_url: str
    messages: Annotated[list, operator.add]


from botocore.config import Config
import boto3

# INCREASE TIMEOUTS FOR LARGE CODE GENERATIONS
my_config = Config(
    read_timeout=300,
    connect_timeout=60,
    retries={"max_attempts": 0}
)
boto_client = boto3.client("bedrock-runtime", region_name=config.AWS_REGION, config=my_config)

llm = ChatBedrockConverse(model=config.BEDROCK_MODEL_ID, temperature=0.1, client=boto_client)


@tool
def retrieve_dynatrace_logs(dt_auth_origin_id: str) -> str:
    """Fetch application logs from Dynatrace for a given dt.auth.origin ID."""
    return fetch_and_save_logs(dt_auth_origin_id)


extractor_llm = llm.bind_tools([retrieve_dynatrace_logs])


def _run_pipeline(incident_number: str, q: queue.Queue):
    """Execute the full RCA pipeline, pushing SSE events to the queue."""
    try:
        # ── Step 1 : Fetch Incident ────────────────────────
        _emit(q, "step", {
            "step": "fetch_incident",
            "status": "running",
            "message": f"Connecting to ServiceNow – fetching {incident_number} …"
        })
        time.sleep(0.5)

        try:
            inc_data = fetch_incident_by_number(incident_number)
            desc = inc_data.get("description", "") or inc_data.get("short_description", "No description found.")
            short_desc = inc_data.get("short_description", "")
            app_key = inc_data.get("u_app_key", "payment-service")
        except Exception as e:
            _emit(q, "step", {
                "step": "fetch_incident",
                "status": "error",
                "message": f"Failed to fetch incident: {e}"
            })
            _emit(q, "done", {"report_html": f"<p class='error'>Error: {e}</p>"})
            return

        _emit(q, "step", {
            "step": "fetch_incident",
            "status": "complete",
            "message": f"Incident fetched successfully"
        })
        _emit(q, "log", {"text": f"📋 Incident: {incident_number}"})
        _emit(q, "log", {"text": f"📝 Short Description: {short_desc}"})
        _emit(q, "log", {"text": f"📄 Description: {desc[:200]}{'…' if len(desc) > 200 else ''}"})
        _emit(q, "log", {"text": f"🔧 App Key: {app_key}"})

        # ── Step 2 : Extract Dynatrace ID ──────────────────
        _emit(q, "step", {
            "step": "extract_id",
            "status": "running",
            "message": "LLM Agent extracting Dynatrace dt.auth.origin ID …"
        })

        import re
        match = re.search(r'(dt0c01\.[a-zA-Z0-9_]+)', desc)
        
        # Use a temp file per request to avoid race conditions
        log_file = tempfile.NamedTemporaryFile(
            suffix=".txt", prefix="rca_logs_", delete=False, mode="w"
        )
        log_file_path = log_file.name
        log_file.close()

        dt_id = match.group(1) if match else "unknown"

        _emit(q, "step", {
            "step": "extract_id",
            "status": "complete",
            "message": f"Extracted ID via Regex: {dt_id}"
        })
        _emit(q, "log", {"text": f"🔑 Extracted Dynatrace Origin ID: {dt_id}"})

        # ── Step 3 : Fetch Logs ────────────────────────
        _emit(q, "step", {
            "step": "fetch_logs",
            "status": "running",
            "message": "Retrieving application logs from Dynatrace mirror..."
        })

        log_status = fetch_and_save_logs(dt_id, output_file=log_file_path)

        _emit(q, "step", {
            "step": "fetch_logs",
            "status": "complete",
            "message": "Logs retrieved and saved"
        })
        _emit(q, "log", {"text": f"📦 {log_status}"})

        # No more else block needed.

        # ── Step 4 : Fetch Code Diffs ──────────────────────
        _emit(q, "step", {
            "step": "fetch_code_diff",
            "status": "running",
            "message": f"Fetching recent GitHub diffs for '{app_key}' …"
        })

        diffs = fetch_recent_code_changes(app_key)

        _emit(q, "step", {
            "step": "fetch_code_diff",
            "status": "complete",
            "message": "Code changes retrieved"
        })
        _emit(q, "log", {"text": f"📂 GitHub diffs fetched for {app_key}"})

        # ── Step 5 : Analyze Logs ──────────────────────────
        _emit(q, "step", {
            "step": "analyze_logs",
            "status": "running",
            "message": "SRE Agent analyzing logs + code diffs – generating RCA report …"
        })

        try:
            with open(log_file_path, "r", encoding="utf-8") as f:
                logs = f.read()
        except FileNotFoundError:
            logs = "(No log file found)"

        sre_system = SystemMessage(content=(
            "You are a **Senior Site Reliability Engineer (SRE)** performing Root Cause Analysis.\n\n"
            "Analyze the application log file provided below. Produce a precise, structured RCA report "
            "in clean Markdown with the following sections:\n\n"
            "## 1. Executive Summary\n"
            "Brief overview of the overall health of the system based on the logs.\n\n"
            "## 2. Errors Identified\n"
            "For each error found, provide:\n"
            "- **File / Service**: which source file or service emitted the error\n"
            "- **Timestamp**: when it occurred\n"
            "- **Error Message**: the exact error text\n"
            "- **Severity**: ERROR / WARN\n\n"
            "## 3. Root Cause Analysis\n"
            "For each error, provide a likely root cause with reasoning.\n\n"
            "## 4. Warnings & Observations\n"
            "Any WARN-level entries or suspicious patterns.\n\n"
            "## 5. Recommended Actions\n"
            "Prioritised action items to resolve the issues (referencing specific source code lines if applicable).\n"
        ))
        sre_human = HumanMessage(
            content=f"--- DYNATRACE LOGS ---\n```\n{logs}\n```\n\n--- RECENT GITHUB CODE CHANGES ---\n```diff\n{diffs}\n```"
        )

        report_response = llm.invoke([sre_system, sre_human])
        report_md = report_response.content

        _emit(q, "step", {
            "step": "analyze_logs",
            "status": "complete",
            "message": "RCA report generated successfully"
        })
        _emit(q, "log", {"text": "✅ Analysis complete"})

        # ── Step 6 : Advanced Remediation (Code Fix + PR) ─────
        _emit(q, "step", {
            "step": "remediate",
            "status": "running",
            "message": "SRE Agent identifying broken file and generating code fix …"
        })

        # 1. Regex to find all broken files in the logs
        import re
        target_files = set()
        matches = re.finditer(r'File "(.*?)", line', logs)
        for match in matches:
            raw_path = match.group(1)
            if os.path.exists(raw_path):
                rel = os.path.relpath(raw_path, os.getcwd())
                target_files.add(rel)
            else:
                tf = os.path.join("src", "services", os.path.basename(raw_path))
                if os.path.exists(tf):
                    target_files.add(tf)
        
        if not target_files:
            import glob
            for tf in glob.glob("src/services/*.py"):
                target_files.add(tf)

        _emit(q, "log", {"text": f"🎯 Identified culprit files: {', '.join(target_files)}"})

        # 2. Fetch local code
        broken_code_context = ""
        for tf in target_files:
            try:
                with open(tf, "r") as f:
                    broken_code_context += f"--- FILE: {tf} ---\n{f.read()}\n\n"
            except:
                pass

        # 3. Ask LLM to fix the code
        fix_prompt_sys = SystemMessage(content=(
            "You are a Senior SRE. Analyze the provided logs and the broken file contents.\n"
            "Generate corrected versions for ALL broken files to fix the interconnected issue.\n"
            "You MUST output a valid JSON object where the keys are the exact file paths provided, and the values are the complete, raw, rewritten file code.\n"
            "Example:\n{\n  \"src/services/app.py\": \"import os\\n...\"\n}\n"
            "Return ONLY the JSON. Do not use markdown blocks like ```json."
        ))
        fix_prompt_human = HumanMessage(content=f"LOGS:\n{logs}\n\nORIGINAL CODE:\n{broken_code_context}")
        
        _emit(q, "log", {"text": "🧠 Generating multi-file code fixes via Bedrock..."})
        fix_response = llm.invoke([fix_prompt_sys, fix_prompt_human])
        
        try:
            import json
            raw_json = fix_response.content.strip()
            if raw_json.startswith("```json"): raw_json = raw_json[7:]
            if raw_json.endswith("```"): raw_json = raw_json[:-3]
            file_patches = json.loads(raw_json.strip())
        except Exception as e:
            _emit(q, "log", {"text": f"⚠️ JSON Parse Failed: {e}"})
            file_patches = {}

        # 4. Push PR
        _emit(q, "log", {"text": f"🚀 Pushing fix to GitHub across {len(file_patches)} files..."})
        pr_url = create_github_pull_request(
            app_key=app_key,
            title=f"AI Fix for {incident_number}: Multi-file Remediation",
            description=report_md[:1000],
            file_patches=file_patches
        )

        _emit(q, "step", {
            "step": "remediate",
            "status": "complete",
            "message": "Remediation complete: PR raised in GitHub"
        })
        _emit(q, "log", {"text": f"🔀 Automated PR: {pr_url}"})

        # Convert markdown to HTML
        report_html = markdown.markdown(
            report_md,
            extensions=["fenced_code", "tables", "nl2br"]
        )

        _emit(q, "done", {
            "report_html": report_html + f"<hr/><h3>Automated PR Raised</h3><p><a href='{pr_url}' target='_blank'>{pr_url}</a></p>",
            "report_md": report_md
        })

        # Cleanup temp log file
        try:
            os.unlink(log_file_path)
        except OSError:
            pass

    except Exception as e:
        tb = traceback.format_exc()
        _emit(q, "step", {"step": "error", "status": "error", "message": str(e)})
        _emit(q, "log", {"text": f"❌ Pipeline error: {e}"})
        _emit(q, "done", {"report_html": f"<pre class='error'>{tb}</pre>"})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Flask Routes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/run/<incident_number>")
def run_pipeline(incident_number: str):
    """SSE endpoint – streams pipeline progress events."""
    q = queue.Queue()

    # Run the pipeline in a background thread
    thread = threading.Thread(target=_run_pipeline, args=(incident_number, q), daemon=True)
    thread.start()

    def event_stream():
        while True:
            try:
                item = q.get(timeout=600)  # 10 min max wait to avoid timeouts on large PRs
                event = item["event"]
                data = json.dumps(item["data"])
                yield f"event: {event}\ndata: {data}\n\n"
                if event == "done":
                    break
            except queue.Empty:
                yield f"event: done\ndata: {json.dumps({'report_html': '<p>Timeout – pipeline took too long.</p>'})}\n\n"
                break

    return Response(event_stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    print("\n🌐  AI RCA Orchestrator running at http://localhost:8080\n")
    app.run(host="0.0.0.0", port=8080, debug=False)

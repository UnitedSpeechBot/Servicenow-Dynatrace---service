# Servicenow-Dynatrace---service
# 🤖 ServiceNow × Dynatrace — AI RCA Orchestrator

An end-to-end, autonomous pipeline that leverages LangGraph and generative AI (AWS Bedrock) to perform rapid Root Cause Analysis (RCA) on production incidents.

## 🌟 The Pipeline

When a ServiceNow incident triggers the agent, it executes a fully automated 6-step workflow:
1. **Fetch Incident**: Pulls real-time incident descriptions directly from the ServiceNow REST API.
2. **Extract ID**: An AI agent parses the human-written description to extract the specific Dynatrace `dt.auth.origin` correlation ID.
3. **Fetch Logs**: Queries the Dynatrace API to retrieve application execution logs associated with the incident.
4. **Fetch Code Diffs**: Reaches out to GitHub to retrieve recent commits and code changes for the affected application.
5. **AI Log Analysis**: A Senior SRE-persona LLM cross-references the application logs against the recent GitHub code diffs to produce a highly structured Markdown RCA report.
6. **Remediation**: The agent automatically creates a Jira Bug Ticket and opens a GitHub Pull Request with the proposed fix.

## 🚀 Quick Start

### 1. Requirements
- Python 3.10+
- A valid AWS Bedrock Model configuration (`anthropic.claude-3-sonnet` or similar)
- API Credentials for ServiceNow, Dynatrace, GitHub, and Jira.

### 2. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/UnitedSpeechBot/Servicenow-Dynatrace---service.git
cd Servicenow-Dynatrace---service

# Recommended: Create a virtual environment
python -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy the sample variables below into a new `.env` file in the root directory:

```env
# ── ServiceNow 
SNOW_INSTANCE=your_instance
SNOW_USER=admin
SNOW_PASSWORD=your_password

# ── AWS Bedrock
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-3-7-sonnet-20250219-v1:0

# ── Dynatrace (Token requires logs.read scope)
DYNATRACE_TOKEN=dt0c01.YOUR_TOKEN_HERE
DYNATRACE_ENV_ID=your_env_id

# ── GitHub
GH_PAT_TOKEN=ghp_YourGitHubTokenHere

# ── Jira 
JIRA_DOMAIN=yourcompany.atlassian.net
JIRA_EMAIL=your.email@company.com
JIRA_API_TOKEN=your_jira_token
JIRA_PROJECT_KEY=DEV
```

*(Note: The application has built-in fallbacks. If Dynatrace, GitHub, or Jira credentials are missing or APIs are unreachable, it will gracefully fall back to executing simulated data for demonstration purposes).*

## 🎮 How to Run

You can run the RCA agent via three different entry points:

### 1. Command Line (CLI)
The fastest way to test a specific incident:
```bash
python main.py INC0010019
```

### 2. Web UI (Dashboard)
Boot up the Flask application with Server-Sent Events (SSE) to view a live, streaming diagnostic dashboard.
```bash
python app.py
```
*Access the dashboard at: `http://localhost:8080`*

### 3. Webhook Server (Automated)
Run a listening server that waits for ServiceNow Business Rules to trigger an outbound REST API call.
```bash
python webhook_server.py
```
*Listens for POST requests at: `http://localhost:5000/api/webhook/servicenow`*

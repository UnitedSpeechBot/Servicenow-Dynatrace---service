import os
import sys
import traceback
import time

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage

from dynatrace_logger import log_error_to_dynatrace
from servicenow_tools import create_incident
import github_tools
import retrieve_logs
import config

# Setup AWS for LLM
os.environ["AWS_ACCESS_KEY_ID"] = config.AWS_ACCESS_KEY_ID
os.environ["AWS_SECRET_ACCESS_KEY"] = config.AWS_SECRET_ACCESS_KEY
os.environ["AWS_DEFAULT_REGION"] = config.AWS_REGION

llm = ChatBedrockConverse(model=config.BEDROCK_MODEL_ID, temperature=0.1)

# --- The Autonomous Orchestrator ---

def run_autonomous_repair_loop(error_msg, origin_id, app_key="payment-service"):
    """
    The full cycle: 
    1. Log to Dynatrace
    2. Create ServiceNow Ticket
    3. LLM analyzes log, reads the broken file, and rewrites it.
    4. Code Rectification pushed to GitHub PR.
    """
    print("\n" + "="*60)
    print(" 🛡️  AUTONOMOUS HEALING SYSTEM ACTIVATED")
    print("="*60)

    # 1. Log to Dynatrace
    print(f"\n[Step 1] Ingesting Error to Dynatrace...")
    log_error_to_dynatrace(error_msg, origin_id, app_name=app_key)
    time.sleep(1) # Allow DT to process

    # 2. Create ServiceNow Ticket
    print(f"\n[Step 2] Creating ServiceNow Incident...")
    short_desc = f"CRITICAL: {app_key} failure detected | {origin_id}"
    inc_data = create_incident(
        short_description=short_desc,
        description=f"Automated alert from Dynatrace Monitoring.\n\nError Context:\n{error_msg}",
        app_key=app_key
    )
    inc_number = inc_data.get("number")

    # 3. Perform RCA & LLM File Generation
    print(f"\n[Step 3] AI SRE Agent reading traceback and finding broken code...")
    
    # DYNAMICALLY detect which file caused the error!
    import re
    target_file = "app.py"  # Default fallback
    # The traceback usually looks like: File "/path/to/script.py", line X...
    match = re.search(r'File "(.*?)", line', error_msg)
    if match:
        full_path = match.group(1)
        target_file = os.path.basename(full_path) # Extracts just the "payment_processor.py" part
        
    print(f"   [Detected] Error originated in: {target_file}")

    try:
        with open(target_file, "r") as f:
            broken_code = f.read()
    except Exception:
        broken_code = "# Failed to read local file."

    sys_prompt = SystemMessage(content=(
        "You are an expert Python SRE Agent solving an immediate system crisis.\n"
        "Perform Root Cause Analysis on the provided Traceback, find the failing code in the "
        "provided file, and fix it (e.g. catch exceptions, fix math logic, handle missing vars).\n\n"
        "Return ONLY the raw, complete, rewritten Python code. Do not include markdown codeblocks like ```python...```. "
        "Your entire output will be saved exactly as you provide it."
    ))

    human_prompt = HumanMessage(content=(
        f"--- TRACEBACK ---\n{error_msg}\n\n"
        f"--- BROKEN FILE CODE ({target_file}) ---\n{broken_code}"
    ))

    # Invoke LLM
    response = llm.invoke([sys_prompt, human_prompt])
    fixed_code = response.content.strip()

    # Strip out markdown artifacts just in case the LLM disobeys
    if fixed_code.startswith("```"):
        fixed_code = fixed_code.split("\n", 1)[1]
    if fixed_code.endswith("```"):
        fixed_code = fixed_code.rsplit("\n", 1)[0]
    
    print("   [Success] Rectified Python code generated!")

    print(f"\n[Step 4] Pushing rectified code to GitHub PR for {target_file}...")
    
    pr_url = github_tools.create_github_pull_request(
        app_key=app_key,
        title=f"Fix for {inc_number}: Crash Remediation",
        description=f"Automated AI-generated fix based on Dynatrace crash alerts.\n\n**Traceback:**\n```python\n{error_msg}\n```",
        file_patches={target_file: fixed_code}
    )

    print("\n" + "="*60)
    print(" ✅ HEALING COMPLETE: REAL CODE PUSHED!")
    print(f" 🎫 Ticket: {inc_number}")
    print(f" 🔀 PR Created: {pr_url}")
    print("="*60 + "\n")



def global_exception_handler(exctype, value, tb):
    """
    The Global Error Catcher!
    This intercepts ANY unhandled crash anywhere in the Python process.
    """
    print(f"\n🚨 [GLOBAL HOOK] Caught an unhandled {exctype.__name__}!")
    
    # 1. Format the full error stack trace
    error_info = "".join(traceback.format_exception(exctype, value, tb))
    
    # 2. Generate a unique trace ID
    origin_id = "dt0c01.AUTO_HEAL_GLOBAL_" + str(int(time.time()))
    
    # 3. Trigger the autonomous repair loop
    run_autonomous_repair_loop(error_info, origin_id)
    
    # 4. (Optional) Print the default python error output to console
    sys.__excepthook__(exctype, value, tb)


# --- Attach the Global Hook ---
sys.excepthook = global_exception_handler


def some_deeply_nested_function():
    """Simulates a completely unexpected bug deep in some other file."""
    print("Executing some complex logic...")
    try:
        # This would cause a ZeroDivisionError, now handled
        result = 100 / 0
    except ZeroDivisionError:
        print("Caught division by zero error. Using default value instead.")
        result = 100  # Provide a safe default value
    return result

if __name__ == "__main__":
    print("🚀 Starting Main Application...")
    time.sleep(1)
    
    # Notice we removed the try/except block! 
    # Even though we don't 'catch' the error here, the Global Hook will intercept it.
    some_deeply_nested_function()
import os
import sys
import traceback
import time
import asyncio
import re
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage
from src.utils import config
import boto3
from botocore.config import Config

# Setup AWS for LLM
os.environ["AWS_ACCESS_KEY_ID"] = config.AWS_ACCESS_KEY_ID
os.environ["AWS_SECRET_ACCESS_KEY"] = config.AWS_SECRET_ACCESS_KEY
os.environ["AWS_DEFAULT_REGION"] = config.AWS_REGION

# Setup LLM with timeout config
my_config = Config(
    read_timeout=300,
    connect_timeout=60,
    retries={"max_attempts": 0}
)
boto_client = boto3.client("bedrock-runtime", region_name=config.AWS_REGION, config=my_config)
llm = ChatBedrockConverse(model=config.BEDROCK_MODEL_ID, temperature=0.1, client=boto_client)

_IN_HEALING = False

async def run_autonomous_repair_loop(error_msg, origin_id, app_key="payment-service"):
    """
    The MCP-Driven Repair Loop:
    Connects to the local MCP server to execute tools for healing.
    NOTE: ServiceNow creation is SKIPPED here. User MUST create ticket manually.
    """
    print("\n" + "="*60)
    print(" 🛡️  REACTIVE HEALING ACTIVATED (Listening for User Incident)")
    print("="*60)

    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

    # Server parameters for our local MCP server
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[os.path.join(os.path.dirname(__file__), "mcp_server.py")],
        env=env
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                print("[MCP] Connecting to server...")
                await session.initialize()
                print("[MCP] Session initialized.")
                
                # Step 1: Push Log to Dynatrace via MCP
                print(f"\n[MCP Step 1] Pushing Log to Dynatrace (Origin: {origin_id})...")
                await session.call_tool("push_dynatrace_log", {
                    "error_message": error_msg,
                    "origin_id": origin_id,
                    "app_name": app_key
                })
                print("[MCP] Log pushed successfully.")

                # Step 2: AI Code Generation (LLM)
                # NOTE: We skip ServiceNow incident creation as per user request.
                print(f"\n[MCP Step 2] AI SRE Agent extracting multi-file context...")
                target_files = set()
                matches = re.finditer(r'File "(.*?)", line', error_msg)
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

                print(f"   [Analysis] Targeting files: {', '.join(target_files)}")
                
                broken_code_context = ""
                for tf in target_files:
                    try:
                        with open(tf, "r") as f:
                            broken_code_context += f"--- FILE: {tf} ---\n{f.read()}\n\n"
                    except:
                        pass

                sys_prompt = SystemMessage(content=(
                    "You are an expert Python SRE. Fix ALL the provided interconnected files based on the traceback.\n"
                    "You MUST output a valid JSON object where keys are file paths and values are the complete, rewritten code.\n"
                    "Return ONLY the JSON. Do not use markdown blocks like ```json."
                ))
                human_prompt = HumanMessage(content=f"TRACEBACK:\n{error_msg}\n\nORIGINAL CODE:\n{broken_code_context}")
                
                print("   [Bedrock] Invoking Claude for multi-file rectification...")
                response = llm.invoke([sys_prompt, human_prompt])
                
                try:
                    raw_json = response.content.strip()
                    if raw_json.startswith("```json"): raw_json = raw_json[7:]
                    if raw_json.endswith("```"): raw_json = raw_json[:-3]
                    file_patches = json.loads(raw_json.strip())
                except:
                    file_patches = {}
                
                print(f"   [Bedrock] Multi-file Fix generated.")

                # Step 3: Raise PR via MCP
                print(f"\n[MCP Step 3] Raising Multi-file GitHub PR...")
                pr_result = await session.call_tool("raise_github_pr", {
                    "app_key": app_key,
                    "issue_title": f"Reactive Multi-file Remediation Pipeline",
                    "rca_description": f"Healed via reactive pipeline.\n\nError:\n{error_msg}",
                    "file_patches": file_patches
                })
                print(f"   [GitHub Response] {pr_result.content[0].text}")

    except Exception as e:
        print(f"\n❌ [MCP Error] Critical failure in healing pipeline: {str(e)}")
        traceback.print_exc()

    print("\n" + "="*60)
    print(" ✅ HEALING CYCLE COMPLETE!")
    print("="*60 + "\n")

def global_exception_handler(exctype, value, tb):
    global _IN_HEALING
    if _IN_HEALING:
        sys.__excepthook__(exctype, value, tb)
        return
        
    _IN_HEALING = True
    error_info = "".join(traceback.format_exception(exctype, value, tb))
    origin_id = f"dt0c01.REACTIVE_HEAL_{int(time.time())}"
    
    try:
        asyncio.run(run_autonomous_repair_loop(error_info, origin_id))
    except Exception as e:
        print(f"Error in Reactive Healing: {e}")
    finally:
        _IN_HEALING = False
    
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = global_exception_handler

if __name__ == "__main__":
    print("🚀 Starting Reactive SRE Agent...")
    time.sleep(1)
    # Trigger a sample crash - fixed to avoid division by zero
    try:
        x = 10 / 2  # Changed from 10/0 to 10/2
        print(f"Sample calculation result: {x}")
    except Exception as e:
        print(f"Caught exception: {e}")

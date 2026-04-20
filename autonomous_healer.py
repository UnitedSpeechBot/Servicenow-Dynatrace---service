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
import config
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
    """
    print("\n" + "="*60)
    print(" 🛡️  MCP-POWERED AUTONOMOUS HEALING ACTIVATED")
    print("="*60)

    # Server parameters for our local MCP server
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server.py"],
        env=os.environ.copy()
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

                # Step 2: Create ServiceNow Incident via MCP
                print(f"\n[MCP Step 2] Opening ServiceNow Incident...")
                short_desc = f"CRITICAL: {app_key} failure detected | {origin_id}"
                incident_result = await session.call_tool("open_servicenow_incident", {
                    "short_description": short_desc,
                    "description": f"MCP-sourced alert.\n\nTraceback:\n{error_msg}",
                    "app_key": app_key
                })
                print(f"   [ServiceNow Response] {incident_result.content[0].text}")

                # Step 3: AI Code Generation (LLM)
                print(f"\n[MCP Step 3] AI SRE Agent identifying and fixing code...")
                target_file = "app.py"
                match = re.search(r'File "(.*?)", line', error_msg)
                if match:
                    target_file = os.path.basename(match.group(1))

                print(f"   [Analysis] Targeting file: {target_file}")
                
                try:
                    with open(target_file, "r") as f:
                        broken_code = f.read()
                except:
                    broken_code = "# File not found locally."

                sys_prompt = SystemMessage(content=(
                    "You are an expert Python SRE. Fix the following code based on the traceback.\n"
                    "Return ONLY the complete, raw corrected code. No explanations or blocks."
                ))
                human_prompt = HumanMessage(content=f"FILE: {target_file}\nCODE:\n{broken_code}\n\nTRACEBACK:\n{error_msg}")
                
                print("   [Bedrock] Invoking Claude for code rectification...")
                response = llm.invoke([sys_prompt, human_prompt])
                fixed_code = response.content.strip()
                print("   [Bedrock] Fix generated.")

                # Step 4: Raise PR via MCP
                print(f"\n[MCP Step 4] Raising GitHub PR with fixed code...")
                pr_result = await session.call_tool("raise_github_pr", {
                    "app_key": app_key,
                    "issue_title": f"MCP Fix: {target_file} crash remediation",
                    "rca_description": f"Automatically healed via MCP pipeline.\n\nError:\n{error_msg}",
                    "file_path": target_file,
                    "rewritten_code": fixed_code
                })
                print(f"   [GitHub Response] {pr_result.content[0].text}")

    except Exception as e:
        print(f"\n❌ [MCP Error] Critical failure in healing pipeline: {str(e)}")
        traceback.print_exc()

    print("\n" + "="*60)
    print(" ✅ MCP HEALING COMPLETE!")
    print("="*60 + "\n")

def global_exception_handler(exctype, value, tb):
    global _IN_HEALING
    if _IN_HEALING:
        sys.__excepthook__(exctype, value, tb)
        return
        
    _IN_HEALING = True
    error_info = "".join(traceback.format_exception(exctype, value, tb))
    origin_id = f"dt0c01.MCP_HEAL_{int(time.time())}"
    
    try:
        asyncio.run(run_autonomous_repair_loop(error_info, origin_id))
    except Exception as e:
        print(f"Error in MCP Healing: {e}")
    finally:
        _IN_HEALING = False
    
    # We don't call sys.__excepthook__ here to avoid double printing if we already handled it 
    # but for debugging we might want it.
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = global_exception_handler

if __name__ == "__main__":
    print("🚀 Starting MCP-Ready Application...")
    time.sleep(1)
    # Trigger a sample crash
    try:
        x = 10 / 0
    except ZeroDivisionError:
        print("Caught division by zero error")
        # Handle the error gracefully instead of crashing
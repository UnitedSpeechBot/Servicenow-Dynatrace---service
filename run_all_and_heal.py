import os
import glob
import subprocess
import time
import signal
from autonomous_healer import run_autonomous_repair_loop

def test_all_files_and_heal():
    """
    The Universal SRE Scanner:
    1. Finds EVERY python file in the directory (even new ones).
    2. Runs them isolated from each other.
    3. If any file crashes, it intercepts the error and raises a PR for it.
    """
    print("="*60)
    print(" 🛠️  ENTERPRISE SRE SCANNER: Testing Entire Repo")
    print("="*60)
    
    # Ignore helper tools and just target the actual services/modules
    ignore_list = [
        "run_all_and_heal.py", "app.py", "config.py", "dynatrace_logger.py",
        "dynatrace_prog.py", "github_tools.py", "jira_tools.py", 
        "retrieve_logs.py", "servicenow_tools.py", "autonomous_healer.py", "main.py", "webhook_server.py"
    ]
    
    py_files = [f for f in glob.glob("*.py") if f not in ignore_list]
    
    print(f"[Scanner] Found {len(py_files)} services to inspect.\n")
    
    for script in py_files:
        print(f"\n▶️ Running {script} ...")
        
        try:
            # Run the file as an isolated process with a timeout
            # This guarantees that if one throws an error or hangs, it doesn't kill this master loop
            result = subprocess.run(
                ["python3", script], 
                capture_output=True, 
                text=True,
                timeout=30  # Add a timeout of 30 seconds to prevent hanging
            )
            
            # Capture the output to analyze if it crashed
            output = result.stderr if result.stderr else result.stdout
            
            # Detect if it failed/crashed
            if result.returncode != 0 or "Exception" in output or "Traceback" in output or "Error" in output:
                print(f"💥 CRASH DETECTED IN {script}!")
                
                # Format a clean traceback so the AI knows EXACTLY which file failed
                if f'File "{script}"' not in output:
                     output = f'Traceback (most recent call last):\n  File "{script}", line 1, in <module>\n' + output
                     
                # Automatically trigger Dynatrace, ServiceNow, and the LLM PR Fix!
                origin_id = f"dt0c01.AUTO_SCAN_{int(time.time())}"
                run_autonomous_repair_loop(output, origin_id, app_key=script.split('.')[0])
                
            else:
                print(f"✅ {script} ran cleanly with no crashes.")
                
        except subprocess.TimeoutExpired:
            print(f"⏱️ {script} timed out after 30 seconds. Skipping to next file.")
            # Optionally, you could still trigger the repair loop for timeouts
            output = f"Timeout error: {script} execution exceeded 30 seconds"
            origin_id = f"dt0c01.AUTO_SCAN_TIMEOUT_{int(time.time())}"
            run_autonomous_repair_loop(output, origin_id, app_key=script.split('.')[0])
            
        except KeyboardInterrupt:
            print("\n⚠️ Keyboard interrupt detected. Exiting gracefully...")
            return
            
        except Exception as e:
            print(f"⚠️ Error running {script}: {str(e)}")

if __name__ == "__main__":
    try:
        test_all_files_and_heal()
    except KeyboardInterrupt:
        print("\n⚠️ Keyboard interrupt detected. Exiting gracefully...")
        exit(0)
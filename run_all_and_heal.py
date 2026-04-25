import os
import glob
import subprocess
import time
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
            # Run the file with a timeout to prevent hanging processes
            result = subprocess.run(
                [os.sys.executable, script], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                text=True,
                timeout=30  # Add a reasonable timeout (30 seconds)
            )
            
            # Print the output
            print(result.stdout)
            
            # Detect if it failed/crashed
            if result.returncode != 0:
                print(f"💥 CRASH DETECTED IN {script}! Passing to SRE Agent...")
                
                # Format a clean traceback so the AI knows EXACTLY which file failed
                output = result.stdout
                if f'File "{script}"' not in output:
                     output = f'Traceback (most recent call last):\n  File "{script}", line 1, in <module>\n' + output
                     
                # Automatically trigger Dynatrace, ServiceNow, and the LLM PR Fix!
                origin_id = f"dt0c01.AUTO_SCAN_{int(time.time())}"
                run_autonomous_repair_loop(output, origin_id, app_key=script.split('.')[0])
                
            else:
                print(f"✅ {script} finished executing.")
                
        except subprocess.TimeoutExpired:
            print(f"⏱️ {script} timed out after 30 seconds. Skipping to next file.")
            continue
        except KeyboardInterrupt:
            print("\n⚠️ Process interrupted by user. Exiting scanner.")
            return
        except Exception as e:
            print(f"⚠️ Error running {script}: {str(e)}")
            continue

if __name__ == "__main__":
    try:
        test_all_files_and_heal()
    except KeyboardInterrupt:
        print("\n⚠️ Scanner interrupted by user. Exiting.")
    except Exception as e:
        print(f"⚠️ Unexpected error in scanner: {str(e)}")
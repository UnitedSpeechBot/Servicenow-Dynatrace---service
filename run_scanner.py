import os
import glob
import subprocess
import time
import asyncio
from src.core.autonomous_healer import run_autonomous_repair_loop

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
    
    ignore_list = []
    
    py_files = [f for f in glob.glob("src/services/*.py") if f not in ignore_list]
    
    print(f"[Scanner] Found {len(py_files)} services to inspect.\n")
    
    for script in py_files:
        print(f"\n▶️ Running {script} ...")
        
        # We use Popen and PYTHONUNBUFFERED so you can see live logs line-by-line!
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONPATH"] = os.path.abspath(os.path.dirname(__file__))

        process = subprocess.Popen(
            [os.sys.executable, script], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            text=True,
            env=env
        )
        
        # Read the output live and print it to the screen instantly
        output_lines = []
        for line in process.stdout:
            print(line, end="")  # Stream it live!
            output_lines.append(line)
            
        process.wait()
        full_output = "".join(output_lines)
        
        # Detect if it failed/crashed
        if process.returncode != 0:
            print(f"\n💥 CRASH DETECTED IN {script}! Passing to SRE Agent...")
            
            # Format a clean traceback so the AI knows EXACTLY which file failed
            if f'File "{script}"' not in full_output:
                 full_output = f'Traceback (most recent call last):\n  File "{script}", line 1, in <module>\n' + full_output
                 
            # Automatically trigger Dynatrace Logs and the LLM PR Fix! (ServiceNow is manual)
            origin_id = f"dt0c01.AUTO_SCAN_{int(time.time())}"
            app_key = os.path.basename(script).replace(".py", "")
            asyncio.run(run_autonomous_repair_loop(full_output, origin_id, app_key=app_key))
        else:
            print(f"✅ {script} finished executing.")

if __name__ == "__main__":
    test_all_files_and_heal()

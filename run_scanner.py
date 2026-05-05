import subprocess
import sys
import time
import logging
import signal
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def test_all_files_and_heal():
    """Tests all Python files and triggers healing if needed."""
    print("\n" + "="*60)
    print("  🔍 Starting System Scanner")
    print("="*60 + "\n")
    
    # Find all Python files in src directory
    src_dir = Path("src")
    if not src_dir.exists():
        logging.error("src directory not found")
        return
    
    python_files = list(src_dir.rglob("*.py"))
    logging.info(f"Found {len(python_files)} Python files to scan")
    
    failed_files = []
    
    for py_file in python_files:
        logging.info(f"Testing {py_file}...")
        
        try:
            # Run the file with a timeout to prevent hanging
            process = subprocess.Popen(
                [sys.executable, str(py_file)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            try:
                # Wait for process with timeout
                stdout, stderr = process.communicate(timeout=30)
                
                if process.returncode != 0:
                    logging.error(f"❌ {py_file} failed with return code {process.returncode}")
                    if stderr:
                        logging.error(f"Error output: {stderr[:500]}")
                    failed_files.append(str(py_file))
                else:
                    logging.info(f"✅ {py_file} passed")
                    
            except subprocess.TimeoutExpired:
                logging.warning(f"⏱️  {py_file} timed out after 30 seconds")
                process.kill()
                process.communicate()
                
        except KeyboardInterrupt:
            logging.info("\n⚠️  Scan interrupted by user")
            if 'process' in locals():
                process.terminate()
                process.wait()
            break
        except Exception as e:
            logging.error(f"Error testing {py_file}: {e}")
            failed_files.append(str(py_file))
    
    # Print summary
    print("\n" + "="*60)
    print("  📊 Scan Summary")
    print("="*60)
    print(f"  Total files scanned: {len(python_files)}")
    print(f"  Failed: {len(failed_files)}")
    if failed_files:
        print("\n  Failed files:")
        for f in failed_files:
            print(f"    - {f}")
    print("="*60 + "\n")
    
    return len(failed_files) == 0

if __name__ == "__main__":
    try:
        success = test_all_files_and_heal()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logging.info("\n⚠️  Scanner interrupted by user")
        sys.exit(130)
    except Exception as e:
        logging.error(f"Scanner failed: {e}")
        sys.exit(1)
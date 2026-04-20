import os
import sys

# Append root directory to sys path so that "src.*" modules can be discovered automatically
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.web.app import app

if __name__ == "__main__":
    print("\n🌐  AI RCA Orchestrator running at http://localhost:8080\n")
    app.run(host="0.0.0.0", port=8080, debug=False)

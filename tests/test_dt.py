import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_dynatrace_connection():
    env_id = os.getenv("DYNATRACE_ENV_ID")
    token = os.getenv("DYNATRACE_TOKEN")
    
    # Construct base URL for SaaS
    url = f"https://{env_id}.live.dynatrace.com/api/v2/logs/search?limit=1"
    
    headers = {
        "Authorization": f"Api-Token {token}",
        "Content-Type": "application/json"
    }
    
    print(f"Testing Dynatrace Connectivity...")
    print(f"URL: {url}")
    print(f"Token starting with: {token[:10]}...")
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            print("✅ SUCCESS: Your Dynatrace ID and Token are working perfectly!")
        else:
            print(f"❌ FAILURE: Received status code {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ ERROR: Could not connect. {e}")

if __name__ == "__main__":
    test_dynatrace_connection()

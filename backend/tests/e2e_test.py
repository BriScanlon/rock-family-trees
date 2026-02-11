import requests
import time
import sys

# Detect backend host based on environment
backend_url = "http://localhost:8000"

def test_e2e():
    print(f"Starting E2E test against {backend_url}")
    
    # 1. Search for an artist
    query = "Iron Maiden"
    print(f"Searching for: {query}")
    search_res = requests.get(f"{backend_url}/search?q={query}")
    if search_res.status_code != 200:
        print(f"Search failed: {search_res.status_code}")
        sys.exit(1)
    
    results = search_res.json()
    if not results:
        print("No results found")
        sys.exit(1)
    
    # Pick the first result (Iron Maiden)
    artist = results[0]
    artist_id = artist['id']
    print(f"Found artist: {artist['name']} ({artist_id})")
    
    # 2. Generate tree
    print("Triggering generation...")
    gen_res = requests.post(f"{backend_url}/generate", json={
        "artist_id": artist_id,
        "depth": 2
    })
    
    if gen_res.status_code != 200:
        print(f"Generation trigger failed: {gen_res.status_code}")
        print(gen_res.text)
        sys.exit(1)
    
    job_id = gen_res.json()['job_id']
    print(f"Job started: {job_id}")
    
    # 3. Poll status
    max_retries = 30
    for i in range(max_retries):
        status_res = requests.get(f"{backend_url}/status/{job_id}")
        data = status_res.json()
        status = data['status']
        progress = data['progress']
        
        print(f"Status: {status} ({progress}%)")
        
        if status == "Completed":
            print("SUCCESS: Generation completed!")
            print(f"Result URL: {data['result_url']}")
            return
        elif status == "Error":
            print(f"FAILED: Job failed with error: {data.get('message')}")
            sys.exit(1)
            
        time.sleep(2)
    
    print("FAILED: Job timed out")
    sys.exit(1)

if __name__ == "__main__":
    test_e2e()

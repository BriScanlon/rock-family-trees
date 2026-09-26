import time

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def wait_for(job_id, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client.get(f"/status/{job_id}").json()
        if status["status"] in ("Completed", "Error"):
            return status
        time.sleep(0.1)
    raise AssertionError("job timed out")


def test_samples_and_offline_search(monkeypatch):
    def boom(self, q):
        raise RuntimeError("offline")
    monkeypatch.setattr(main.MusicBrainzClient, "search_artists", boom)
    assert client.get("/samples").json()[0]["id"] == "demo:yardbirds"
    results = client.get("/api/search", params={"q": "yardbirds"}).json()
    assert results[0]["id"] == "demo:yardbirds"
    assert client.get("/search", params={"q": "zzz"}).status_code == 502


def test_generate_demo_end_to_end():
    job = client.post("/generate", json={"artist_id": "demo:yardbirds", "depth": 3, "title": "Yardbirds!"}).json()
    status = wait_for(job["job_id"])
    assert status["status"] == "Completed", status
    assert status["stats"]["bands"] >= 8
    svg = client.get(status["result_url"])
    assert svg.status_code == 200 and svg.headers["content-type"].startswith("image/svg+xml")
    assert "Yardbirds!" in svg.text
    assert client.get(f"/api/tree/{job['job_id']}").json()["tree"]["title"] == "Yardbirds!"


def test_errors_are_reported():
    job = client.post("/generate", json={"artist_id": "demo:nobody"}).json()
    status = wait_for(job["job_id"])
    assert status["status"] == "Error" and "not found" in status["message"]
    assert client.get("/status/doesnotexist").status_code == 404
    assert client.post("/generate", json={"artist_id": "x", "depth": 9}).status_code == 422

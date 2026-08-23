import urllib.request
import json

API_BASE = "http://127.0.0.1:5000"

def test_stats():
    req = urllib.request.Request(f"{API_BASE}/api/stats")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    
    print("GET /api/stats response:")
    print(json.dumps(data, indent=2))
    
    assert "total" in data
    assert "high" in data
    assert "medium" in data
    assert "low" in data
    assert "today" in data
    assert data["total"] > 0
    print(f"\n[OK] Stats endpoint returned total={data['total']}, high={data['high']}, medium={data['medium']}, low={data['low']}, today={data['today']}")

if __name__ == "__main__":
    test_stats()

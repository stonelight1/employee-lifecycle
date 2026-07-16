"""Test work-items endpoint"""
import sys
sys.path.insert(0, '.')
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Test work-items
resp = client.get('/api/work-items')
print(f'Status: {resp.status_code}')
if resp.status_code != 200:
    print(f'Body: {resp.text[:1000]}')
else:
    data = resp.json()
    print(f'OK: {len(data.get("data",{}).get("items",[]))} items')

# Test probation employees
resp2 = client.get('/api/probation/employees')
print(f'Probation Status: {resp2.status_code}')
if resp2.status_code != 200:
    print(f'Body: {resp2.text[:1000]}')
else:
    data = resp2.json()
    print(f'OK: {len(data.get("data",{}).get("items",[]))} items')

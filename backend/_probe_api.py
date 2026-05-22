import sys
sys.path.insert(0, r'C:\Users\VIJAY SALVATORE\Desktop\Projects\RAG\backend')

import requests
BASE = 'http://localhost:8000'
USER_ID = 'test-user-123'

def show(label, r):
    print(f'\n── {label} ──')
    print(f'  status  : {r.status_code}')
    try:
        d = r.json()
        if isinstance(d, list):
            print(f'  type    : list[{len(d)}]')
            if d: print(f'  keys[0] : {list(d[0].keys())}')
            if d: print(f'  sample  : {d[0]}')
        else:
            print(f'  type    : {type(d).__name__}')
            print(f'  keys    : {list(d.keys()) if isinstance(d,dict) else "N/A"}')
            print(f'  sample  : {str(d)[:300]}')
    except:
        print(f'  raw     : {r.text[:200]}')

# 1. List sessions
show('GET /sessions', requests.get(f'{BASE}/api/v1/chat/sessions', params={'user_id': USER_ID}, timeout=5))

# 2. Try create session
show('POST /sessions', requests.post(
    f'{BASE}/api/v1/chat/sessions',
    json={'user_id': USER_ID, 'title': 'test'},
    timeout=5,
))

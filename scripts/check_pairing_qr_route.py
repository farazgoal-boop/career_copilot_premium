from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from web_app.app import create_app

app = create_app()
client = app.test_client()
response = client.get('/api/pairing/qr/123456')
print(f'STATUS={response.status_code}')
print(f'CONTENT_TYPE={response.content_type}')
print(f'BODY_PREFIX={response.get_data(as_text=True)[:80]!r}')

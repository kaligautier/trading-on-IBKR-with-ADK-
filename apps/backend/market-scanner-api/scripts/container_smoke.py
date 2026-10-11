"""Boot the release image and exercise HTTP inside it without cloud credentials."""

import subprocess
import sys
import uuid

name = "reader-smoke-" + uuid.uuid4().hex[:8]
image = sys.argv[1] if len(sys.argv) > 1 else "local/market-scanner-api:review"
try:
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-d",
            "--name",
            name,
            "-e",
            "DATABASE_URL=postgresql://market_scanner_reader:unused@localhost/scanner",
            "-e",
            "API_TOKEN=container-smoke-token",
            image,
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "docker",
            "exec",
            name,
            "python",
            "-c",
            """
import json, time, urllib.request, urllib.error
for attempt in range(50):
    try:
        response = urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=1)
        assert response.status == 200
        break
    except OSError:
        time.sleep(.1)
else:
    raise AssertionError('Image did not become healthy')
try:
    urllib.request.urlopen('http://127.0.0.1:8080/market-scans/latest')
    raise AssertionError('Anonymous report access was allowed')
except urllib.error.HTTPError as error:
    assert error.code == 401
request = urllib.request.Request(
    'http://127.0.0.1:8080/schemas/report-v3.json',
    headers={'Authorization':'Bearer container-smoke-token'},
)
assert '$defs' in json.load(urllib.request.urlopen(request))
print('Container HTTP health, authentication and packaged schema passed')
""",
        ],
        check=True,
    )
finally:
    subprocess.run(["docker", "stop", name], check=False, capture_output=True)

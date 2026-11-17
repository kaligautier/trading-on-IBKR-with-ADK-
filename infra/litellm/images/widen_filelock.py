"""Backport the installed requirement bound from upstream LiteLLM PR #49137."""

import base64
import csv
import hashlib
import importlib.metadata
import io


distribution = importlib.metadata.distribution("litellm")
metadata = next(p for p in distribution.files if str(p).endswith(".dist-info/METADATA"))
path = distribution.locate_file(metadata)
original = path.read_text()
old = "Requires-Dist: filelock>=3.16.1,<4.0"
new = "Requires-Dist: filelock>=3.16.1,<5"
assert original.count(old) == 1, "Upstream metadata changed; review this backport"
content = original.replace(old, new).encode()
path.write_bytes(content)
# Keep the wheel installation's integrity manifest accurate after the backport.
record = path.with_name("RECORD")
rows = list(csv.reader(io.StringIO(record.read_text())))
for row in rows:
    if row[0] == str(metadata):
        digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=")
        row[1:] = ["sha256=" + digest.decode(), str(len(content))]
with record.open("w", newline="") as output:
    csv.writer(output).writerows(rows)

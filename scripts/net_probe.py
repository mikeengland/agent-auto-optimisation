"""Diagnose why calls to the Anthropic API fail from a given environment (temporary debugging aid).

Prints only whether secrets are set (never their values), proxy settings with credentials stripped,
DNS/TLS reachability, and the full exception chain from a real SDK call.
"""

import os
import re
import socket
import sys

print("python", sys.version.split()[0])

SHOW_VALUE = ("PROXY", "SSL_CERT", "REQUESTS_CA", "NODE_EXTRA")
for k in sorted(os.environ):
    u = k.upper()
    if any(s in u for s in ("PROXY", "ANTHROPIC", "SSL_CERT", "REQUESTS_CA", "NODE_EXTRA", "CLAUDE", "SANDBOX")):
        v = os.environ[k]
        if any(s in u for s in SHOW_VALUE) or u == "ANTHROPIC_BASE_URL":
            print(f"env {k}: {re.sub(r'//[^@/]*@', '//***@', v)[:120]!r}")  # proxy creds stripped
        else:
            print(f"env {k}: set={bool(v)} len={len(v)}")  # never print values

for host in ("api.anthropic.com", "github.com", "pypi.org"):
    try:
        addrs = sorted({a[4][0] for a in socket.getaddrinfo(host, 443)})[:3]
        print(f"dns {host}: {addrs}")
    except Exception as e:  # noqa: BLE001
        print(f"dns {host}: FAILED {e!r}")

sys.path.insert(0, ".")
from app import config  # noqa: E402

key = config.anthropic_api_key()
print("app config sees an API key:", bool(key))

import anthropic  # noqa: E402

try:
    models = anthropic.Anthropic(api_key=key or "missing", max_retries=0, timeout=15).models.list(limit=1)
    print("anthropic SDK call OK:", [m.id for m in models.data])
except Exception as e:  # noqa: BLE001
    print("anthropic SDK call FAILED:", repr(e))
    cause, depth = e.__cause__, 0
    while cause is not None and depth < 6:
        print("  caused by:", repr(cause))
        cause, depth = cause.__cause__, depth + 1

"""Test the deployed NGINX allowlist against a deliberately permissive upstream."""

import re
import secrets
import time
import urllib.error
import urllib.request

from smoke import ROOT, docker, image


UPSTREAM = """
from http.server import BaseHTTPRequestHandler, HTTPServer
import time
class Handler(BaseHTTPRequestHandler):
    def do_GET(self): self.do_POST()
    def do_POST(self):
        self.send_response(200)
        self.end_headers()
        if "streamGenerateContent" in self.path:
            for chunk in [b"data: FIRST\\n\\n", b"data: LAST\\n\\n"]:
                self.wfile.write(chunk)
                self.wfile.flush()
                time.sleep(0.5)
        else:
            self.wfile.write(self.headers.get("Authorization", "anonymous").encode())
    def log_message(self, *args): pass
HTTPServer(("0.0.0.0", 4001), Handler).serve_forever()
"""


def main():
    prefix = "litellm-routes-" + secrets.token_hex(4)
    upstream, gateway = prefix + "-upstream", prefix + "-gateway"
    variables = (ROOT / "gateway_routes.tf").read_text()
    digest = re.search(r'default\s*=\s*"(sha256:[0-9a-f]{64})"', variables)[1]
    gateway_image = "ghcr.io/nginx/nginx-unprivileged@" + digest
    try:
        docker(
            "run",
            "-d",
            "--name",
            upstream,
            "-p",
            "127.0.0.1::4000",
            "--entrypoint",
            "python",
            image("proxy_digest", "litellm"),
            "-c",
            UPSTREAM,
        )
        docker(
            "create",
            "--name",
            gateway,
            "--network",
            "container:" + upstream,
            "--entrypoint",
            "nginx",
            gateway_image,
            "-c",
            "/tmp/gateway-nginx.conf",
            "-g",
            "daemon off;",
        )
        docker(
            "cp",
            str(ROOT / "config/gateway-nginx.conf"),
            gateway + ":/tmp/gateway-nginx.conf",
        )
        docker("start", gateway)
        base = "http://" + docker("port", upstream, "4000/tcp")

        def request(route, method="GET", auth=None):
            headers = {"Authorization": "Bearer " + auth} if auth else {}
            req = urllib.request.Request(base + route, method=method, headers=headers)
            try:
                return urllib.request.urlopen(req, timeout=5)
            except urllib.error.HTTPError as error:
                return error

        for _ in range(30):
            try:
                if request("/health/readiness").status == 200:
                    break
            except OSError:
                pass
            time.sleep(0.2)
        else:
            raise RuntimeError("Gateway did not become ready")

        # Even admin credentials cannot reach a login, UI or unlisted route.
        for route in [
            "/",
            "/ui",
            "/ui/",
            "/login",
            "/v2/login",
            "/v3/login",
            "/sso/login",
            "/sso/callback",
            "/user/new",
            "/key/info",
            "/docs",
            "/openapi.json",
            "/%6cogin",
            "/ui%2flogin",
            "/v1/chat/completions",
            "/v1beta/models/model:futureMethod",
        ]:
            for auth in [None, "synthetic-admin-key"]:
                for method in ["GET", "POST"]:
                    with request(route, method, auth) as response:
                        assert response.status == 404, (route, method, response.status)
        for route in [
            "/key/generate",
            "/key/delete",
            "/v1beta/models/model:generateContent",
            "/v1beta/models/model:countTokens",
        ]:
            with request(route, "POST", "synthetic-client-key") as response:
                assert response.status == 200
                assert response.read() == b"Bearer synthetic-client-key"
            with request(route, "GET") as response:
                assert response.status == 405
        with request("/v1beta/models/model:streamGenerateContent", "POST") as response:
            started = time.monotonic()
            assert response.readline() == b"data: FIRST\n"
            assert time.monotonic() - started < 0.4, "SSE was buffered"
            assert b"data: LAST" in response.read()
        print(
            "PASS: gateway denies login/UI/admin routes; allowed routes preserve auth and stream SSE",
            flush=True,
        )
    finally:
        docker("rm", "-f", gateway, upstream, check=False)


if __name__ == "__main__":
    main()

"""Local Gemini HTTP provider boundary; never contacts an external service."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import time


def response(text, finished=True):
    result = {
        "candidates": [
            {"content": {"parts": [{"text": text}], "role": "model"}, "index": 0}
        ],
        "modelVersion": "gemini-2.5-flash",
    }
    if finished:
        result["candidates"][0]["finishReason"] = "STOP"
        result["usageMetadata"] = {
            "promptTokenCount": 10,
            "candidatesTokenCount": 20,
            "totalTokenCount": 30,
        }
    return result


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if not any(
            method in self.path
            for method in [":generateContent", ":streamGenerateContent"]
        ):
            self.send_error(404)
            return
        stream = ":streamGenerateContent" in self.path
        self.send_response(200)
        self.send_header(
            "Content-Type", "text/event-stream" if stream else "application/json"
        )
        self.end_headers()
        if stream:
            for index, chunk in enumerate(
                [response("NATIVE_", False), response("STREAM_OK")]
            ):
                self.wfile.write(b"data: " + json.dumps(chunk).encode() + b"\n\n")
                self.wfile.flush()
                if index == 0:
                    time.sleep(1)
        else:
            self.wfile.write(json.dumps(response("NATIVE_OK")).encode())

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()

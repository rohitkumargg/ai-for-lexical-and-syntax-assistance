import pytest
import sys
import os
import socket
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

def test_abrupt_client_disconnect_handled_safely():
    """Verify that an abrupt client disconnect on TCP socket does not crash the server."""
    host = "127.0.0.1"
    port = 5000

    # Ensure port 5000 is accepting connections
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, port))
    except ConnectionRefusedError:
        pytest.skip(f"Server not running on {host}:{port}")

    payload = json.dumps({
        "code": "int main() { return 0; }",
        "filename": "disconnect_test.c",
        "language": "c"
    })
    http_req = (
        f"POST /api/coordinator/analyze_and_plan HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(payload)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
        f"{payload}"
    )
    sock.sendall(http_req.encode("utf-8"))
    # Abruptly close the socket without reading the response
    sock.close()

    # Verify server is still alive and accepting subsequent connections
    sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock2.connect((host, port))
    sock2.close()

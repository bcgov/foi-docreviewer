"""Synthetic record-format peer, available during CLI and WSGI startup."""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from cryptography.hazmat.primitives.asymmetric import rsa
import jwt

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
public.update(kid="fixture-key", use="sig", alg="RS256")
responses = {
    "/formats": {
        "conversion": [".docx"],
        "dedupe": [".pdf"],
        "nonredactable": [".mp3"],
    },
    "/jwks": {"keys": [public]},
    "/config": {
        "issuer": "http://fixtures:8080/realm",
        "jwks_uri": "http://fixtures:8080/jwks",
    },
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in responses:
            self.send_error(404)
            return
        body = json.dumps(responses[self.path]).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()

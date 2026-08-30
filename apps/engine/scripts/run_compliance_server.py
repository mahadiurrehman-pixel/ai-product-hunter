#!/usr/bin/env python3
"""
REHU eBay Compliance Server.

Lightweight, zero-dependency HTTP server that exposes the Marketplace
Account Deletion notification endpoint required by eBay for Production
keyset activation.

Uses only Python standard library (http.server, json, urllib).
No FastAPI, no uvicorn, no additional dependencies required.

Usage:
    python scripts/run_compliance_server.py

With ngrok for eBay testing:
    # Terminal 1:
    python scripts/run_compliance_server.py
    # Terminal 2:
    ngrok http 8080
    # Copy the https://xxxx.ngrok-free.app URL
    # Set EBAY_NOTIFICATION_ENDPOINT_URL in .env
    # Paste into eBay Developer Portal
"""
from __future__ import annotations

import json
import os
import sys
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Ensure project root is on path
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from services.ebay.compliance import (
    EbayComplianceHandler,
    ComplianceConfig,
)
from utils.logger import get_logger

logger = get_logger(__name__)

# Global handler instance (initialized in main)
_handler: EbayComplianceHandler | None = None


class ComplianceHTTPHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler for eBay compliance endpoints.

    Routes:
        GET  /ebay/notifications?challenge_code=...  → Challenge verification
        POST /ebay/notifications                     → Deletion notification
        GET  /health                                 → Health check
    """

    def log_message(self, format, *args):
        """Override to use our logger instead of stderr."""
        logger.debug(f"Compliance HTTP: {format % args}")

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            self._send_json(200, {
                "status": "healthy",
                "service": "rehu-compliance",
                "configured": _handler.config.is_configured,
                "environment": _handler.config.environment,
            })
            return

        if parsed.path == "/ebay/notifications":
            start = time.time()
            params = parse_qs(parsed.query)
            challenge_code = params.get("challenge_code", [""])[0]

            try:
                result = _handler.handle_challenge(
                    {"challenge_code": challenge_code}
                )
                elapsed = time.time() - start
                logger.info(
                    f"Challenge verified in {elapsed:.3f}s (limit: 3.0s)"
                )
                self._send_json(200, result)
            except ValueError as e:
                self._send_json(400, {"error": str(e)})
            except Exception as e:
                logger.error(f"Challenge error: {e}")
                self._send_json(500, {"error": "Internal server error"})
            return

        self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/ebay/notifications":
            start = time.time()

            # Read raw body BEFORE parsing (required for signature verification)
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length) if content_length > 0 else b""

            # Extract signature header
            signature = self.headers.get("X-EBAY-SIGNATURE", "")

            # Parse JSON
            try:
                payload = json.loads(raw_body) if raw_body else {}
            except json.JSONDecodeError:
                logger.warning("Received malformed JSON notification")
                self._send_json(400, {
                    "status": "error",
                    "message": "Invalid JSON",
                })
                return

            # Process notification (signature verified inside handler)
            try:
                result = _handler.handle_notification(
                    payload=payload,
                    raw_body=raw_body,
                    signature_header=signature,
                )
                elapsed = time.time() - start

                if elapsed > 2.5:
                    logger.warning(
                        f"Notification took {elapsed:.3f}s "
                        f"(approaching 3.0s eBay limit)"
                    )

                # Always return 200 to prevent eBay retry storms
                self._send_json(200, {"status": "acknowledged"})

            except Exception as e:
                logger.error(f"Notification error: {e}")
                # Still return 200 to prevent retry storms
                self._send_json(200, {"status": "acknowledged"})
            return

        self._send_json(404, {"error": "Not found"})

    def _send_json(self, status_code: int, data: dict):
        """Send a JSON response."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    global _handler

    config = ComplianceConfig.from_settings()
    _handler = EbayComplianceHandler(config=config)

    port = int(os.environ.get("COMPLIANCE_PORT", "8080"))

    print("=" * 60)
    print("REHU eBay Compliance Server")
    print("=" * 60)
    print(f"Environment:    {config.environment}")
    print(f"Configured:     {config.is_configured}")
    print(f"Endpoint URL:   {config.endpoint_url or 'NOT SET'}")
    print(f"Token set:      {'Yes' if config.verification_token else 'NO'}")
    print(f"Listen:         0.0.0.0:{port}")
    print("=" * 60)

    if not config.is_configured:
        print()
        print("WARNING: Not fully configured. Set these in .env:")
        print("  EBAY_VERIFICATION_TOKEN=<from eBay Developer Portal>")
        print("  EBAY_NOTIFICATION_ENDPOINT_URL=<public HTTPS URL>")
        print()

    server = ThreadingHTTPServer(("0.0.0.0", port), ComplianceHTTPHandler)
    logger.info(f"Compliance server listening on 0.0.0.0:{port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down compliance server.")
        server.shutdown()


if __name__ == "__main__":
    main()
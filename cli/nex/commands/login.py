"""NEX CLI — Browser OAuth 2.0 PKCE Login Command (RFC 7636 / RFC 8252)."""

import base64
import hashlib
import logging
import secrets
import socket
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Annotated

import typer
from rich.panel import Panel

from nex.client.django import NexDjangoClient
from nex.client.exceptions import NexClientError
from nex.core.context import CLIContext
from nex.core.credentials import save_credentials
from nex.core.exceptions import NexError
from nex.core.exit_codes import ExitCode
from nex.output.json import print_json_success
from nex.output.terminal import console

logger = logging.getLogger(__name__)

SUCCESS_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>NEX CLI Authenticated</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace; background: #0B0B0F; color: #F3F4F6; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0;">
  <div style="background: #14141E; border: 2px solid #6366F1; padding: 40px; border-radius: 8px; text-align: center; max-width: 480px; box-shadow: 0 20px 40px rgba(0,0,0,0.6);">
    <h1 style="color: #06B6D4; font-size: 20px; font-weight: bold; margin-top: 0; letter-spacing: 0.05em;">AUTHENTICATION COMPLETE</h1>
    <p style="color: #9CA3AF; font-size: 13px; line-height: 1.6;">Your browser identity has authorized the local NEX Command-Line Interface.</p>
    <div style="margin-top: 24px; padding: 12px; background: rgba(16, 185, 129, 0.1); border: 1px solid #10B981; border-radius: 4px; color: #10B981; font-size: 13px; font-weight: bold;">
      ✓ You may safely close this tab and return to your terminal.
    </div>
  </div>
</body>
</html>
"""

ERROR_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>NEX CLI Authentication Error</title>
</head>
<body style="font-family: monospace; background: #0B0B0F; color: #EF4444; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0;">
  <div style="background: #14141E; border: 2px solid #EF4444; padding: 40px; border-radius: 8px; text-align: center; max-width: 480px;">
    <h1 style="color: #EF4444; font-size: 20px; margin-top: 0;">AUTHENTICATION REJECTED</h1>
    <p style="color: #9CA3AF; font-size: 13px;">Authorization was denied or state validation failed.</p>
    <p style="color: #6B7280; font-size: 12px;">Please return to your terminal and run 'nex login' again.</p>
  </div>
</body>
</html>
"""


class CallbackResult:
    """Thread-safe holder for loopback callback data."""

    def __init__(self) -> None:
        self.code: str | None = None
        self.state: str | None = None
        self.error: str | None = None
        self.event = threading.Event()


def make_handler(
    expected_state: str, result: CallbackResult
) -> type[BaseHTTPRequestHandler]:
    """Factory creating an ephemeral loopback HTTP handler."""

    class CallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            # Suppress default stdout log noise from HTTPServer
            pass

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/callback":
                self.send_response(404)
                self.end_headers()
                return

            params = urllib.parse.parse_qs(parsed.query)
            error_param = params.get("error", [None])[0]
            code_param = params.get("code", [None])[0]
            state_param = params.get("state", [None])[0]

            if error_param:
                result.error = error_param
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(ERROR_HTML.encode("utf-8"))
                result.event.set()
                return

            if not state_param or state_param != expected_state:
                result.error = "State mismatch (possible CSRF attack)."
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(ERROR_HTML.encode("utf-8"))
                result.event.set()
                return

            result.code = code_param
            result.state = state_param

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(SUCCESS_HTML.encode("utf-8"))
            result.event.set()

    return CallbackHandler


def login(
    ctx: typer.Context,
    manual: Annotated[
        bool,
        typer.Option(
            "--manual", help="Do not attempt to open system browser automatically."
        ),
    ] = False,
    frontend_url: Annotated[
        str,
        typer.Option(
            "--frontend-url",
            envvar="NEX_FRONTEND_URL",
            help="Base URL for the NEX Web Application.",
        ),
    ] = "http://localhost:3000",
) -> None:
    """Authenticate the NEX CLI via Web Browser OAuth with PKCE (RFC 7636 / RFC 8252)."""
    cli_ctx: CLIContext = ctx.obj

    # Generate PKCE parameters
    code_verifier = secrets.token_urlsafe(
        64
    )  # 86 characters, RFC 7636 compliant (43-128 chars)
    verifier_digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = (
        base64.urlsafe_b64encode(verifier_digest).decode("ascii").rstrip("=")
    )
    state = secrets.token_urlsafe(32)

    # Spawn loopback server on 127.0.0.1 on port 0 (OS picks available ephemeral port)
    result = CallbackResult()
    handler_class = make_handler(state, result)

    try:
        server = HTTPServer(("127.0.0.1", 0), handler_class)
    except OSError as err:
        raise NexError(
            f"Failed to bind loopback HTTP server: {err}",
            exit_code=ExitCode.GENERAL_ERROR,
            suggestion="Verify 127.0.0.1 interface is up and firewall permits local loopback binding.",
        ) from err

    port = server.server_port
    redirect_uri = f"http://127.0.0.1:{port}/callback"

    # Start loopback server in daemon thread
    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    hostname = socket.gethostname()
    query_params = urllib.parse.urlencode(
        {
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "redirect_uri": redirect_uri,
            "state": state,
            "device_name": f"{hostname} (CLI)",
        }
    )
    auth_url = f"{frontend_url.rstrip('/')}/auth/cli?{query_params}"

    if not cli_ctx.json_mode:
        console.print()
        console.print(
            Panel(
                f"[bold #6366F1]NEX CLI AUTHENTICATION GATEWAY[/bold #6366F1]\n\n"
                f"[#A1A1B5]Opening your web browser to approve terminal credentials...[/#A1A1B5]\n\n"
                f"[dim]If your browser does not open automatically, copy and paste this URL into your browser:[/dim]\n\n"
                f"[bold underline #06B6D4]{auth_url}[/bold underline #06B6D4]\n\n"
                f"[dim]Awaiting authorization on local loopback interface (port {port})...[/dim]",
                title="[bold #06B6D4]NEX AUTH[/bold #06B6D4]",
                border_style="#6366F1",
            )
        )

    if not manual:
        try:
            webbrowser.open(auth_url)
        except Exception:
            pass

    # Wait up to 120 seconds for user to authenticate
    authorized = result.event.wait(timeout=120)
    server.server_close()

    if not authorized:
        raise NexError(
            "Authentication timed out after 120 seconds without browser authorization.",
            exit_code=ExitCode.AUTH_ERROR,
            suggestion="Run 'nex login' again and approve the consent screen promptly.",
        )

    if result.error or not result.code:
        raise NexError(
            f"Authentication failed: {result.error or 'No authorization code received.'}",
            exit_code=ExitCode.AUTH_ERROR,
            suggestion="Ensure you are logged into NEX and approve the terminal request.",
        )

    # Exchange authorization code + PKCE verifier with Django backend
    backend_url = cli_ctx.config.api.base_url
    with NexDjangoClient(base_url=backend_url) as client:
        try:
            token_response = client.request(
                "POST",
                "/auth/cli/token/",
                json={
                    "code": result.code,
                    "code_verifier": code_verifier,
                    "redirect_uri": redirect_uri,
                    "device_name": f"{hostname} (CLI)",
                },
            )
        except NexClientError as exc:
            raise NexError(
                f"Token exchange failed: {exc.message}",
                exit_code=ExitCode.AUTH_ERROR,
                suggestion="Verify the Django backend is running and healthy.",
            ) from exc

    access_token = token_response.get("access_token")
    user_info = token_response.get("user", {})

    if not access_token:
        raise NexError(
            "Token exchange succeeded but no access token was returned by the server.",
            exit_code=ExitCode.AUTH_ERROR,
        )

    # Persist in OS Keyring / fallback vault
    save_credentials(access_token, user_info)

    if cli_ctx.json_mode:
        print_json_success(
            "login",
            {
                "status": "authenticated",
                "email": user_info.get("email"),
                "role": user_info.get("role"),
                "token_type": "Bearer",
            },
            cli_ctx.correlation_id,
        )
    else:
        email = user_info.get("email", "unknown")
        role = user_info.get("role", "member")
        console.print()
        console.print(
            f"[bold #10B981]✓ AUTHENTICATED SUCCESSFULLY[/bold #10B981] as [bold #06B6D4]{email}[/bold #06B6D4] "
            f"([#F59E0B]{role.upper()}[/#F59E0B])"
        )
        console.print(
            "  [#A1A1B5]Credentials saved to secure OS vault. All CLI commands will now authenticate seamlessly.[/#A1A1B5]"
        )
        console.print()

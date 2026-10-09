"""Which host a request is on, and the three public origins (subdomain split
spec, decisions 19–31).

DOMAIN is the one setting the domain is written in. Every absolute URL the
backend writes — a mail link, the Google/Microsoft callback, Stripe's return
URLs, the CORS allow-list — is built here from it. The request's Host header
only ever *selects* one of the three origins: it is never copied into a URL,
so a forged Host cannot put its own name into a reset link.
"""
from flask import current_app, has_request_context, request

# The root shows the landing, cv is « J'ai une cible », voyage is le voyage.
APPS = ("root", "cv", "voyage")
_PREFIX = {"root": "", "cv": "cv.", "voyage": "voyage."}


def origin(app: str, config=None) -> str:
    """`{scheme}://{prefix}{DOMAIN}{:port}` for "root", "cv" or "voyage".
    `config` defaults to the current app's; create_app passes its own,
    before an app context exists."""
    cfg = current_app.config if config is None else config
    port = f":{cfg['PUBLIC_PORT']}" if cfg["PUBLIC_PORT"] else ""
    return f"{cfg['PUBLIC_SCHEME']}://{_PREFIX[app]}{cfg['DOMAIN']}{port}"


def origins(config=None) -> list[str]:
    """The three origins, root first: the CORS allow-list (decision 32)."""
    return [origin(app, config) for app in APPS]


def cookie_domain(domain: str) -> str | None:
    """The session cookies' Domain: the whole DOMAIN, so one sign-in covers
    every host (decision 25). None for a single-label name such as
    localhost, which browsers refuse as a cookie domain: the attribute would
    only lose the cookie (decision 26)."""
    return domain if "." in domain else None


def app_of_host(host: str | None, domain: str) -> str | None:
    """"root", "cv" or "voyage" for a Host header value, None for any other
    name. Case, the port and a trailing dot are ignored."""
    name = (host or "").strip().lower().partition(":")[0].rstrip(".")
    for app in APPS:
        if name == _PREFIX[app] + domain:
            return app
    return None


def request_app() -> str | None:
    """The app of the request being served. None outside a request (a
    background run, a CLI command) and on any other name."""
    if not has_request_context():
        return None
    return app_of_host(request.host, current_app.config["DOMAIN"])


def request_origin() -> str:
    """The origin of cv or voyage when the request is on one of them, cv's
    otherwise: the root (it serves no sign-in page), an unknown or forged
    name, no request at all (decision 31)."""
    app = request_app()
    return origin(app if app in ("cv", "voyage") else "cv")

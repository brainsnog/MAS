"""
URL redaction — DEF-04.

Every source this project queries that carries a credential as a query
parameter (OS Places API, confirmed — see property_resolver.py) must have
its captured request URL passed through `redact_url` before it is stored
anywhere destined for an evidence manifest or a dissertation appendix.
Gemini/Groq calls are body/header-based, not query-string, so they should
never hit this path in practice — the parameter name set below is kept
broad anyway, since a wrong assumption here is a credential leak, not a
cosmetic bug.

Query-string (and fragment) redaction works on the raw string, substituting
only matched parameter *values*, rather than parsing with parse_qsl and
rebuilding with urlencode — the round trip through urlencode re-percent-
encodes the whole query string, which would corrupt captured Bristol ArcGIS
URLs (commas in `geometry=-2.604062,51.452073`) into a stored evidence URL
that no longer matches what was actually sent. See
tests/test_redaction.py's round-trip fidelity test against a real captured
fixture URL.

Pairs are split on `&` only, deliberately not also on `;`: Hackney's WFS CQL
filter values contain literal semicolons and parentheses
(`SRID=4326;POINT(-0.05 51.5)`), and splitting on `;` would tear a single
parameter's value into fragments and corrupt it, the same class of damage
urlencode re-escaping would cause.

The fragment is redacted with the same logic as the query string (some APIs,
e.g. OAuth implicit flow, put `key=value` pairs after `#`) even though none
of this project's current sources use one — cheap to cover, and the cost of
being wrong here is a leaked credential, not a cosmetic bug.

Fails closed: this function's failure mode is a leaked credential, so any
unexpected error returns a hard-redacted marker rather than any part of the
original input, which might itself be (or contain) the thing that failed to
redact.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

_SENSITIVE_PARAM_NAMES = {
    "key",
    "api_key",
    "apikey",
    "subscription-key",
    "subscription_key",
    "token",
    "access_token",
    "sig",
    "signature",
    "password",
    "pwd",
    "auth",
    "secret",
    "client_secret",
}

_UNPARSEABLE_MARKER = "REDACTED_UNPARSEABLE_URL"


def _redact_pairs_string(pairs_string: str) -> str:
    """Redact a `name=value&name=value` string. See module docstring for
    why splitting is on `&` only, never also on `;`."""
    if not pairs_string:
        return pairs_string
    parts = []
    for part in pairs_string.split("&"):
        name, sep, value = part.partition("=")
        if sep and name.lower() in _SENSITIVE_PARAM_NAMES:
            parts.append(f"{name}=REDACTED")
        else:
            parts.append(part)
    return "&".join(parts)


def redact_url(url: str) -> str:
    # urlsplit() accepts non-str input silently rather than raising —
    # urlsplit(None) returns an empty bytes-typed SplitResult, and a bytes
    # URL is processed as bytes all the way through, where name.lower()
    # compares bytes against a set of str and never matches. A bytes URL
    # carrying a credential would therefore round-trip unredacted. The
    # except branch below never fires for these, so the type must be
    # guarded explicitly. Confirmed directly: urlsplit(b"...?key=secret")
    # reconstructs byte-identical via urlunsplit, credential intact — see
    # tests/test_redaction.py's bytes-input test.
    if not isinstance(url, str):
        return _UNPARSEABLE_MARKER
    try:
        parts = urlsplit(url)
        if parts.username or parts.password:
            hostport = parts.hostname or ""
            if parts.port:
                hostport = f"{hostport}:{parts.port}"
            netloc = f"REDACTED:REDACTED@{hostport}"
        else:
            netloc = parts.netloc
        redacted_query = _redact_pairs_string(parts.query)
        redacted_fragment = _redact_pairs_string(parts.fragment)
        return urlunsplit((parts.scheme, netloc, parts.path, redacted_query, redacted_fragment))
    except Exception:
        return _UNPARSEABLE_MARKER

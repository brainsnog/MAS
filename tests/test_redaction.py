"""
Tests for src/redaction.py (DEF-04).
"""
from src.redaction import redact_url

# Real captured request URL, from tests/fixtures/discovery/MANIFEST.tsv —
# not a hand-written approximation. No credential-bearing parameter, so a
# correct redact_url must return it character-for-character unchanged; if
# urlencode-style re-escaping were used instead, the comma in `geometry`
# would come back percent-encoded and this would fail.
_REAL_BRISTOL_ARCGIS_URL = (
    "https://maps2.bristol.gov.uk/server2/rest/services/ext/"
    "ll_environment_and_planning/MapServer/2/query?geometry=-2.604062,51.452073"
    "&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects"
    "&outFields=*&returnGeometry=false&f=json"
)


def test_os_places_key_is_redacted():
    url = "https://api.os.uk/search/places/v1/find?query=122+Whiteladies+Road&key=abcd1234secret&dataset=DPA"
    redacted = redact_url(url)
    assert "abcd1234secret" not in redacted
    assert "key=REDACTED" in redacted
    assert "query=122+Whiteladies+Road" in redacted
    assert "dataset=DPA" in redacted


def test_real_bristol_arcgis_url_round_trips_character_identical_apart_from_nothing_to_redact():
    # No sensitive parameter present, so nothing should change at all — this
    # is the fidelity test: any re-encoding pass would alter the comma in
    # `geometry` even though there's nothing to redact.
    assert redact_url(_REAL_BRISTOL_ARCGIS_URL) == _REAL_BRISTOL_ARCGIS_URL


def test_hackney_cql_filter_semicolon_and_parens_survive_untouched():
    url = (
        "https://map2.hackney.gov.uk/geoserver/ows?service=WFS&version=2.0.0"
        "&request=GetFeature&typeName=planning:tpo_point_as_area"
        "&CQL_FILTER=DWITHIN(geom,SRID=4326;POINT(-0.0574934 51.547983),15,meters)"
        "&outputFormat=application/json"
    )
    assert redact_url(url) == url


def test_url_with_no_query_string_is_unchanged():
    url = "https://maps2.bristol.gov.uk/server2/rest/services/ext"
    assert redact_url(url) == url


def test_malformed_url_fails_closed_rather_than_leaking_input():
    # Confirmed directly against python 3.11's urlsplit: this raises
    # ValueError("Invalid IPv6 URL") inside urlsplit itself, so this
    # genuinely exercises the except branch, not passing for an unrelated
    # reason.
    malformed = "https://[not-a-valid-host/:::key=supersecret"
    redacted = redact_url(malformed)
    assert "supersecret" not in redacted
    assert redacted == "REDACTED_UNPARSEABLE_URL"


def test_malformed_port_fails_closed_rather_than_leaking_input():
    # Confirmed directly: urlsplit() itself succeeds here, but accessing
    # .port raises ValueError("Port could not be cast to integer value as
    # 'notaport'") — this is the case that exercises the try block via
    # attribute access, not urlsplit() itself.
    malformed = "https://alice:hunter2@example.invalid:notaport/path?key=SECRET"
    redacted = redact_url(malformed)
    assert "hunter2" not in redacted
    assert "SECRET" not in redacted
    assert redacted == "REDACTED_UNPARSEABLE_URL"


def test_none_input_fails_closed_rather_than_raising():
    redacted = redact_url(None)  # type: ignore[arg-type]
    assert redacted == "REDACTED_UNPARSEABLE_URL"


def test_bytes_input_carrying_a_credential_fails_closed_rather_than_leaking_it():
    # The case that actually matters: urlsplit() accepts bytes input
    # silently, and without the explicit type guard, name.lower() would
    # compare bytes against a set of str, never match, and the credential
    # would round-trip unredacted. Confirmed directly against python 3.11
    # before this guard existed — see the Deviation Log, 2026-08-06.
    redacted = redact_url(b"https://api.os.uk/find?key=supersecret")  # type: ignore[arg-type]
    assert "supersecret" not in redacted
    assert redacted == "REDACTED_UNPARSEABLE_URL"


def test_mixed_case_parameter_name_is_still_redacted():
    url = "https://api.os.uk/search/places/v1/find?Query=x&KEY=supersecret&Dataset=DPA"
    redacted = redact_url(url)
    assert "supersecret" not in redacted
    assert "KEY=REDACTED" in redacted


def test_repeated_key_parameter_redacts_every_occurrence():
    url = "https://example.invalid/path?key=first-secret&other=1&key=second-secret"
    redacted = redact_url(url)
    assert "first-secret" not in redacted
    assert "second-secret" not in redacted
    assert redacted.count("key=REDACTED") == 2


def test_netloc_basic_auth_credentials_are_redacted():
    url = "https://alice:hunter2@example.invalid:8443/path?x=1"
    redacted = redact_url(url)
    assert "hunter2" not in redacted
    assert "alice" not in redacted
    assert redacted == "https://REDACTED:REDACTED@example.invalid:8443/path?x=1"


def test_fragment_with_credential_shaped_pair_is_redacted():
    url = "https://example.invalid/callback#access_token=supersecrettoken&type=bearer"
    redacted = redact_url(url)
    assert "supersecrettoken" not in redacted
    assert "access_token=REDACTED" in redacted
    assert "type=bearer" in redacted

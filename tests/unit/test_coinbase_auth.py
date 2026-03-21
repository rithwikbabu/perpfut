import base64
import json

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from perpfut.exchange_coinbase import CoinbaseJWTTokenProvider


def _generate_ec_private_key_pem() -> str:
    private_key = ec.generate_private_key(ec.SECP256R1())
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def test_build_rest_token_contains_expected_request_claims() -> None:
    provider = CoinbaseJWTTokenProvider(
        api_key_id="organizations/test/apiKeys/key-123",
        api_key_secret=_generate_ec_private_key_pem(),
    )

    token = provider.build_rest_token("GET", "/api/v3/brokerage/intx/portfolio/portfolio-123")

    header = jwt.get_unverified_header(token)
    payload = jwt.decode(token, options={"verify_signature": False})

    assert header["alg"] == "ES256"
    assert header["kid"] == "organizations/test/apiKeys/key-123"
    assert payload["sub"] == "organizations/test/apiKeys/key-123"
    assert payload["uri"] == "GET api.coinbase.com/api/v3/brokerage/intx/portfolio/portfolio-123"
    assert payload["exp"] - payload["nbf"] == 120


def test_build_rest_token_handles_escaped_newlines() -> None:
    pem = _generate_ec_private_key_pem().replace("\n", "\\n")
    provider = CoinbaseJWTTokenProvider(
        api_key_id="organizations/test/apiKeys/key-123",
        api_key_secret=pem,
    )

    token = provider.build_rest_token("GET", "/api/v3/brokerage/accounts")

    payload_segment = token.split(".")[1]
    padded_payload = payload_segment + "=" * ((4 - len(payload_segment) % 4) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded_payload.encode("utf-8")))
    assert payload["uri"] == "GET api.coinbase.com/api/v3/brokerage/accounts"

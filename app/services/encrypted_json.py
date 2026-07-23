import base64
import hashlib
import hmac
import json
import os
import secrets
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


KEY_ENV_NAME = "FSS_DATA_ENCRYPTION_KEY"
FORMAT_PREFIX = "FSS2."
LEGACY_FORMAT_PREFIX = "FSS1."
NONCE_SIZE = 12
LEGACY_NONCE_SIZE = 16
LEGACY_TAG_SIZE = 32
MINIMUM_KEY_LENGTH = 32
ASSOCIATED_DATA = b"FSS encrypted JSON v2"

# Used only to read old insecure FSS1 files once. Stores immediately rewrite
# them as FSS2; this key is never used for new encryption.
LEGACY_DEVELOPMENT_KEY = b"fss-local-data-obfuscation-key-change-me"


class EncryptedJsonError(RuntimeError):
    """Raised when encrypted JSON cannot be authenticated or decrypted."""


class EncryptedJsonCodec:
    """Authenticated JSON encryption backed by AES-256-GCM."""

    def __init__(self, encryption_key: str | bytes | None = None):
        configured_key = encryption_key
        if configured_key is None:
            configured_key = os.getenv(KEY_ENV_NAME)
        if isinstance(configured_key, str):
            configured_key = configured_key.encode("utf-8")
        if not configured_key or len(configured_key) < MINIMUM_KEY_LENGTH:
            raise EncryptedJsonError(
                f"{KEY_ENV_NAME} must contain at least {MINIMUM_KEY_LENGTH} bytes."
            )

        self._source_key = configured_key
        self._aesgcm = AESGCM(
            hashlib.sha256(b"FSS AES-256-GCM key v2\0" + configured_key).digest()
        )

    def dumps(self, data: Any) -> str:
        plaintext = json.dumps(
            data, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        nonce = secrets.token_bytes(NONCE_SIZE)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, ASSOCIATED_DATA)
        return FORMAT_PREFIX + base64.urlsafe_b64encode(
            nonce + ciphertext
        ).decode("ascii")

    def loads(self, content: str) -> tuple[Any, bool]:
        """Return (document, needs_rewrite) for encrypted or legacy content."""
        stripped = content.strip()
        if not stripped:
            raise json.JSONDecodeError("Empty JSON document", content, 0)
        if stripped.startswith(("{", "[")):
            return json.loads(stripped), True
        if stripped.startswith(LEGACY_FORMAT_PREFIX):
            return self._load_legacy(stripped), True
        if not stripped.startswith(FORMAT_PREFIX):
            raise EncryptedJsonError("지원하지 않는 암호화 저장 형식입니다.")

        payload = self._decode_payload(stripped[len(FORMAT_PREFIX):])
        if len(payload) < NONCE_SIZE + 16:
            raise EncryptedJsonError("암호화 저장 파일이 너무 짧습니다.")
        try:
            plaintext = self._aesgcm.decrypt(
                payload[:NONCE_SIZE], payload[NONCE_SIZE:], ASSOCIATED_DATA
            )
            return json.loads(plaintext.decode("utf-8")), False
        except InvalidTag as error:
            raise EncryptedJsonError(
                "저장 파일을 복호화하지 못했습니다. "
                f"{KEY_ENV_NAME} 값과 파일 무결성을 확인하세요."
            ) from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise EncryptedJsonError("복호화된 저장 데이터가 올바른 JSON이 아닙니다.") from error

    @staticmethod
    def _decode_payload(encoded: str) -> bytes:
        try:
            return base64.b64decode(encoded, altchars=b"-_", validate=True)
        except (ValueError, UnicodeEncodeError) as error:
            raise EncryptedJsonError("암호화 저장 파일의 인코딩이 손상되었습니다.") from error

    def _load_legacy(self, content: str) -> Any:
        payload = self._decode_payload(content[len(LEGACY_FORMAT_PREFIX):])
        if len(payload) < LEGACY_NONCE_SIZE + LEGACY_TAG_SIZE:
            raise EncryptedJsonError("암호화 저장 파일이 너무 짧습니다.")
        nonce = payload[:LEGACY_NONCE_SIZE]
        ciphertext = payload[LEGACY_NONCE_SIZE:-LEGACY_TAG_SIZE]
        supplied_tag = payload[-LEGACY_TAG_SIZE:]

        for candidate_key in (self._source_key, LEGACY_DEVELOPMENT_KEY):
            material = hashlib.sha512(b"FSS encrypted JSON v1\0" + candidate_key).digest()
            expected = hmac.digest(material[32:], nonce + ciphertext, "sha256")
            if not hmac.compare_digest(supplied_tag, expected):
                continue
            plaintext = self._legacy_xor(ciphertext, nonce, material[:32])
            try:
                return json.loads(plaintext.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise EncryptedJsonError("기존 저장 데이터가 올바른 JSON이 아닙니다.") from error
        raise EncryptedJsonError(
            "기존 저장 파일을 복호화하지 못했습니다. "
            f"{KEY_ENV_NAME} 값을 확인하세요."
        )

    @staticmethod
    def _legacy_xor(data: bytes, nonce: bytes, key: bytes) -> bytes:
        result = bytearray(len(data))
        for offset in range(0, len(data), 32):
            block = hmac.digest(
                key, nonce + (offset // 32).to_bytes(8, "big"), "sha256"
            )
            for index, value in enumerate(data[offset:offset + 32]):
                result[offset + index] = value ^ block[index]
        return bytes(result)

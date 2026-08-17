import os
import uuid

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

from .exceptions import CryptoError


class CryptoManager:
    DATA_KEY_AAD = b"KryptoNote.DEK.v2"
    PAYLOAD_AAD_PREFIX = b"KryptoNote.Payload.v3"
    ITEM_FIELDS = frozenset(
        {
            "title",
            "text_content",
            "thumbnail",
            "full_data",
            "original_filename",
            "media_metadata",
        }
    )
    KDF_NAME = "argon2id"
    KDF_ITERATIONS = 4
    KDF_MEMORY_COST = 1024 * 128
    KDF_LANES = 4
    KDF_ITERATIONS_RANGE = (1, 20)
    KDF_MEMORY_COST_RANGE = (8 * 1024, 512 * 1024)
    KDF_LANES_RANGE = (1, 16)

    def __init__(self):
        self.key = None

    def derive_key(self, password: str, salt: bytes = None):
        """Legacy API: derive and load the payload key directly from password."""
        if salt is None:
            salt = os.urandom(16)
        else:
            salt = self.normalize_salt(salt)

        self.key = self.derive_password_key(password, salt)
        return salt

    @classmethod
    def derive_password_key(
        cls,
        password: str,
        salt: bytes,
        iterations=None,
        memory_cost=None,
        lanes=None,
    ) -> bytes:
        salt = cls.normalize_salt(salt)
        iterations = cls.KDF_ITERATIONS if iterations is None else int(iterations)
        memory_cost = cls.KDF_MEMORY_COST if memory_cost is None else int(memory_cost)
        lanes = cls.KDF_LANES if lanes is None else int(lanes)
        cls.validate_kdf_params(iterations, memory_cost, lanes)
        kdf = Argon2id(
            salt=salt,
            length=32,
            iterations=iterations,
            memory_cost=memory_cost,
            lanes=lanes,
        )
        return kdf.derive(password.encode())

    @classmethod
    def validate_kdf_params(cls, iterations, memory_cost, lanes):
        values = (
            ("iterations", int(iterations), cls.KDF_ITERATIONS_RANGE),
            ("memory_cost", int(memory_cost), cls.KDF_MEMORY_COST_RANGE),
            ("lanes", int(lanes), cls.KDF_LANES_RANGE),
        )
        for name, value, (minimum, maximum) in values:
            if not minimum <= value <= maximum:
                raise CryptoError(
                    f"Invalid Argon2 {name}: expected {minimum}..{maximum}, got {value}"
                )

    @staticmethod
    def normalize_salt(salt) -> bytes:
        if salt is None:
            raise CryptoError("Salt is required")
        if isinstance(salt, memoryview):
            return bytes(salt)
        if isinstance(salt, bytearray):
            return bytes(salt)
        if isinstance(salt, bytes):
            return salt
        if isinstance(salt, str):
            text = salt.strip()
            try:
                return uuid.UUID(text).bytes
            except ValueError:
                return text.encode("utf-8")
        raise CryptoError("Invalid salt type")

    @staticmethod
    def generate_data_key() -> bytes:
        return os.urandom(32)

    def load_data_key(self, data_key: bytes):
        if not data_key or len(data_key) != 32:
            raise CryptoError("Invalid data key")
        self.key = bytes(data_key)

    @classmethod
    def wrap_data_key(cls, data_key: bytes, password_key: bytes) -> bytes:
        if not data_key or len(data_key) != 32:
            raise CryptoError("Invalid data key")
        if not password_key or len(password_key) != 32:
            raise CryptoError("Invalid password key")
        nonce = os.urandom(12)
        aesgcm = AESGCM(password_key)
        return nonce + aesgcm.encrypt(nonce, data_key, cls.DATA_KEY_AAD)

    @classmethod
    def unwrap_data_key(cls, wrapped_data_key: bytes, password_key: bytes) -> bytes:
        if not wrapped_data_key or len(wrapped_data_key) < 29:
            raise CryptoError("Invalid wrapped data key")
        if not password_key or len(password_key) != 32:
            raise CryptoError("Invalid password key")
        nonce = wrapped_data_key[:12]
        ciphertext = wrapped_data_key[12:]
        aesgcm = AESGCM(password_key)
        data_key = aesgcm.decrypt(nonce, ciphertext, cls.DATA_KEY_AAD)
        if len(data_key) != 32:
            raise CryptoError("Invalid unwrapped data key")
        return data_key

    @classmethod
    def item_aad(cls, item_id, field) -> bytes:
        if field not in cls.ITEM_FIELDS:
            raise CryptoError(f"Unsupported encrypted item field: {field}")
        return cls._context_aad("item", int(item_id), field)

    @classmethod
    def chunk_aad(cls, item_id, chunk_index) -> bytes:
        return cls._context_aad("chunk", int(item_id), int(chunk_index))

    @classmethod
    def tag_aad(cls, tag_id) -> bytes:
        return cls._context_aad("tag", int(tag_id), "name")

    @classmethod
    def auth_check_aad(cls) -> bytes:
        return cls._context_aad("metadata", "auth_check")

    @classmethod
    def _context_aad(cls, *parts) -> bytes:
        encoded = [cls.PAYLOAD_AAD_PREFIX]
        for part in parts:
            value = str(part).encode("utf-8")
            encoded.append(str(len(value)).encode("ascii") + b":" + value)
        return b"\0".join(encoded)

    def encrypt(self, data: bytes, *, aad: bytes) -> bytes:
        if not aad:
            raise CryptoError("Encryption context is required")
        return self._encrypt(data, aad)

    def decrypt(self, data: bytes, *, aad: bytes) -> bytes:
        if not aad:
            raise CryptoError("Decryption context is required")
        return self._decrypt(data, aad)

    def encrypt_legacy(self, data: bytes) -> bytes:
        return self._encrypt(data, None)

    def decrypt_legacy(self, data: bytes) -> bytes:
        return self._decrypt(data, None)

    def _encrypt(self, data: bytes, aad) -> bytes:
        if not self.key:
            raise CryptoError("Encryption key not loaded")
        if not isinstance(data, bytes):
            data = bytes(data)
        nonce = os.urandom(12)
        aesgcm = AESGCM(self.key)
        return nonce + aesgcm.encrypt(nonce, data, aad)

    def _decrypt(self, data: bytes, aad) -> bytes:
        if not self.key:
            raise CryptoError("Decryption key not loaded")
        if not isinstance(data, bytes):
            data = bytes(data)
        if len(data) < 28:
            raise CryptoError("Invalid encrypted payload")
        nonce = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(self.key)
        return aesgcm.decrypt(nonce, ciphertext, aad)

    def create_clone(self):
        """Create a new CryptoManager with the same key for thread-safe use."""
        clone = CryptoManager()
        if self.key:
            clone.key = bytes(self.key)
        return clone

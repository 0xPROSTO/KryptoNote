import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

from .exceptions import CryptoError


class CryptoManager:
    DATA_KEY_AAD = b"KryptoNote.DEK.v2"
    KDF_NAME = "argon2id"
    KDF_ITERATIONS = 4
    KDF_MEMORY_COST = 1024 * 128
    KDF_LANES = 4

    def __init__(self):
        self.key = None

    def derive_key(self, password: str, salt: bytes = None):
        """Legacy API: derive and load the payload key directly from password."""
        if salt is None:
            salt = os.urandom(16)

        self.key = self.derive_password_key(password, salt)
        return salt

    @classmethod
    def derive_password_key(cls, password: str, salt: bytes) -> bytes:
        kdf = Argon2id(
            salt=salt,
            length=32,
            iterations=cls.KDF_ITERATIONS,
            memory_cost=cls.KDF_MEMORY_COST,
            lanes=cls.KDF_LANES,
        )
        return kdf.derive(password.encode())

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

    def encrypt(self, data: bytes) -> bytes:
        if not self.key:
            raise CryptoError("Encryption key not loaded")
        nonce = os.urandom(12)
        aesgcm = AESGCM(self.key)
        return nonce + aesgcm.encrypt(nonce, data, None)

    def decrypt(self, data: bytes) -> bytes:
        if not self.key:
            raise CryptoError("Decryption key not loaded")
        nonce = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(self.key)
        return aesgcm.decrypt(nonce, ciphertext, None)

    def create_clone(self):
        """Create a new CryptoManager with the same key for thread-safe use."""
        clone = CryptoManager()
        if self.key:
            clone.key = bytes(self.key)
        return clone

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id


class CryptoManager:
    def __init__(self):
        self.key = None

    def derive_key(self, password: str, salt: bytes = None):
        if not salt:
            salt = os.urandom(16)

        kdf = Argon2id(
            salt=salt,
            length=32,
            iterations=4,
            memory_cost=1024 * 128,
            lanes=4,
        )
        self.key = kdf.derive(password.encode())
        return salt

    def encrypt(self, data: bytes) -> bytes:
        if not self.key: raise Exception("Key not loaded")
        nonce = os.urandom(12)
        aesgcm = AESGCM(self.key)
        return nonce + aesgcm.encrypt(nonce, data, None)

    def decrypt(self, data: bytes) -> bytes:
        if not self.key: raise Exception("Key not loaded")
        nonce = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(self.key)
        return aesgcm.decrypt(nonce, ciphertext, None)

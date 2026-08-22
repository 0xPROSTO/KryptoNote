from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from ..constants import MEDIA_CHUNK_SIZE
from ..exceptions import OperationCancelledError
from .connection import READY_STORAGE_STATE


_GCM_NONCE_SIZE = 12
_GCM_TAG_SIZE = 16
_GCM_OVERHEAD = _GCM_NONCE_SIZE + _GCM_TAG_SIZE


def legacy_full_data_plain_size(connection, item_id):
    """Return the plaintext size of a ready legacy payload without loading it."""
    row = connection.execute(
        "SELECT length(full_data) FROM items "
        "WHERE id=? AND storage_state=?",
        (int(item_id), READY_STORAGE_STATE),
    ).fetchone()
    if not row or row[0] is None:
        return None
    encrypted_size = int(row[0])
    if encrypted_size < _GCM_OVERHEAD:
        raise ValueError(
            f"Invalid encrypted full_data for node {int(item_id)}"
        )
    return encrypted_size - _GCM_OVERHEAD


def iter_decrypted_legacy_full_data(
    connection,
    crypto,
    item_id,
    *,
    cancel_check=None,
):
    """Yield one authenticated legacy payload in bounded plaintext blocks."""
    item_id = int(item_id)
    plain_size = legacy_full_data_plain_size(connection, item_id)
    if plain_size is None:
        return

    blobopen = getattr(connection, "blobopen", None)
    if blobopen is None:
        raise RuntimeError(
            "Streaming legacy media requires sqlite3.Connection.blobopen"
        )

    encrypted_size = plain_size + _GCM_OVERHEAD
    with blobopen("items", "full_data", item_id, readonly=True) as blob:
        if len(blob) != encrypted_size:
            raise ValueError(
                f"Legacy media node {item_id} changed while being read"
            )
        nonce = blob.read(_GCM_NONCE_SIZE)
        blob.seek(encrypted_size - _GCM_TAG_SIZE)
        tag = blob.read(_GCM_TAG_SIZE)
        if len(nonce) != _GCM_NONCE_SIZE or len(tag) != _GCM_TAG_SIZE:
            raise ValueError(
                f"Truncated encrypted full_data for node {item_id}"
            )

        decryptor = Cipher(
            algorithms.AES(crypto.key), modes.GCM(nonce, tag)
        ).decryptor()
        decryptor.authenticate_additional_data(
            crypto.item_aad(item_id, "full_data")
        )

        blob.seek(_GCM_NONCE_SIZE)
        remaining = plain_size
        while remaining:
            if cancel_check and cancel_check():
                raise OperationCancelledError("Legacy media read cancelled")
            read_size = min(MEDIA_CHUNK_SIZE, remaining)
            encrypted_part = blob.read(read_size)
            if len(encrypted_part) != read_size:
                raise ValueError(
                    f"Truncated encrypted full_data for node {item_id}"
                )
            remaining -= read_size
            plaintext = decryptor.update(encrypted_part)
            if plaintext:
                yield plaintext

        if cancel_check and cancel_check():
            raise OperationCancelledError("Legacy media read cancelled")
        final_plaintext = decryptor.finalize()
        if final_plaintext:
            yield final_plaintext


def read_decrypted_legacy_prefix(
    connection,
    crypto,
    item_id,
    *,
    limit=64,
    cancel_check=None,
):
    """Read a bounded prefix, but authenticate the complete GCM payload."""
    if limit < 0:
        raise ValueError("Prefix limit must be non-negative")
    if legacy_full_data_plain_size(connection, item_id) is None:
        return None

    prefix = bytearray()
    for chunk in iter_decrypted_legacy_full_data(
        connection,
        crypto,
        item_id,
        cancel_check=cancel_check,
    ):
        if len(prefix) < limit:
            prefix.extend(chunk[:limit - len(prefix)])
    return bytes(prefix)

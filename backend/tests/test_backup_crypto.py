"""Encrypted streaming artifacts fail closed without damaging existing files."""

import pytest
from fs.core.backup import BackupError, decrypt, encrypt, private_file


def test_stream_roundtrip_and_tamper_cleanup(tmp_path):
    plain = tmp_path / "plain"
    encrypted = tmp_path / "encrypted"
    restored = tmp_path / "restored"
    data = b"synthetic-private-content" * 100000
    plain.write_bytes(data)
    key = b"a" * 32
    encrypt(plain, encrypted, key)
    assert b"synthetic-private-content" not in encrypted.read_bytes()
    assert encrypted.stat().st_mode & 0o777 == 0o600
    decrypt(encrypted, restored, key)
    assert restored.read_bytes() == data
    restored.unlink()
    raw = bytearray(encrypted.read_bytes())
    raw[50] ^= 1
    encrypted.write_bytes(raw)
    with pytest.raises(BackupError):
        decrypt(encrypted, restored, key)
    assert not restored.exists()


def test_wrong_key_existing_output_and_size_bound(tmp_path):
    plain = tmp_path / "plain"
    plain.write_bytes(b"synthetic")
    encrypted = tmp_path / "encrypted"
    encrypt(plain, encrypted, b"a" * 32)
    target = tmp_path / "target"
    target.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        decrypt(encrypted, target, b"a" * 32)
    assert target.read_bytes() == b"keep"
    target.unlink()
    with pytest.raises(BackupError):
        decrypt(encrypted, target, b"b" * 32)
    assert not target.exists()
    with pytest.raises(BackupError):
        decrypt(encrypted, target, b"a" * 32, max_bytes=1)
    plain.chmod(0o644)
    with pytest.raises(BackupError):
        private_file(plain)
    link = tmp_path / "link"
    link.symlink_to(encrypted)
    with pytest.raises(BackupError):
        private_file(link)

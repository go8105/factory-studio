"""Read a staged storage copy; no remote credentials or release approval."""

import hashlib
import os
import stat
from datetime import timedelta

from fs.gw.operating_contract import backup_is_current, timestamp, verify_evidence

MAX_ARTIFACT_BYTES = 1024**3


def inspect_copy(path, document, **context):
    """Bind a complete file read to a current signed BACKUP proof.

    A staged file cannot prove storage independence, durability or decryption.
    Never accept a caller's digest as a substitute for reading the bytes.
    """
    if set(document) != {"envelope", "signature"}:
        raise ValueError("invalid proof")
    proof = verify_evidence(document["envelope"], document["signature"], **context)
    if (
        proof.kind != "BACKUP"
        or proof.result != "PASS"
        or timestamp(proof.finished_at) > context["now"] + timedelta(seconds=30)
        or not backup_is_current(proof, context["policy"], context["now"])
    ):
        raise ValueError("current backup required")
    # Check the opened descriptor, preventing final-component symlink swaps.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as source:
        before = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.geteuid()
            or before.st_mode & 0o077
            or not 0 < before.st_size <= MAX_ARTIFACT_BYTES
        ):
            raise ValueError("private bounded regular file required")
        digest = hashlib.sha256()
        count = 0
        while block := source.read(1024**2):
            count += len(block)
            if count > MAX_ARTIFACT_BYTES:
                raise ValueError("copy exceeds limit")
            digest.update(block)
        after = os.fstat(source.fileno())
        if count != before.st_size or (
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError("copy changed while reading")
    return {
        "version": 1,
        "state": "MATCH"
        if digest.hexdigest() == proof.metrics.artifact_digest
        else "MISMATCH",
        "bytesRead": count,
        "artifactDigest": digest.hexdigest(),
        "backupRunId": proof.run_id,
        "storageIndependenceConfirmed": False,
        "decryptionConfirmed": False,
    }

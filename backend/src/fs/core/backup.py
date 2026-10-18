"""Offline database backup primitives. No business authorization or HTTP interface."""

import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

MAGIC = b"FSBACK01"
CHUNK = 1024 * 1024
MAX_BYTES = 1024 * 1024 * 1024


class BackupError(Exception):
    """Non-secret operational failure. Never attach database URLs or subprocess logs."""


def private_file(path, *, size=None):
    path = Path(path)
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_mode & 0o077
        or info.st_uid != os.geteuid()
    ):
        raise BackupError("파일을 운영자 소유의 비공개 일반 파일(0600)로 준비하세요.")
    if size is not None and info.st_size != size:
        raise BackupError("별도 키 파일의 크기를 확인하세요.")
    return path


def private_directory(path):
    path = Path(path)
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.geteuid()
        or info.st_mode & 0o077
    ):
        raise BackupError("작업·보관 폴더를 운영자 소유 0700으로 준비하세요.")
    return path


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        while block := source.read(CHUNK):
            digest.update(block)
    return digest.hexdigest()


def create_private(path):
    private_directory(Path(path).parent)
    return os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb")


def encrypt(source, destination, key):
    if len(key) != 32:
        raise BackupError("백업 암호화 키는32바이트여야 합니다.")
    nonce = os.urandom(12)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(MAGIC)
    with open(source, "rb") as src, create_private(destination) as out:
        out.write(MAGIC + nonce)
        while block := src.read(CHUNK):
            out.write(encryptor.update(block))
        out.write(encryptor.finalize())
        out.write(encryptor.tag)
        out.flush()
        os.fsync(out.fileno())
    descriptor = os.open(Path(destination).parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def decrypt(source, destination, key, *, max_bytes=MAX_BYTES):
    from cryptography.exceptions import InvalidTag

    size = Path(source).stat().st_size
    if size < 36 or size > max_bytes + 36:
        raise BackupError("백업 파일 크기 또는 허용 한도를 확인하세요.")
    created = False
    try:
        with open(source, "rb") as src, create_private(destination) as out:
            created = True
            if src.read(8) != MAGIC:
                raise BackupError("지원하는 백업 형식이 아닙니다.")
            nonce = src.read(12)
            src.seek(-16, os.SEEK_END)
            tag = src.read(16)
            src.seek(20)
            decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
            decryptor.authenticate_additional_data(MAGIC)
            remaining = size - 36
            while remaining:
                block = src.read(min(CHUNK, remaining))
                if not block:
                    raise BackupError("잘린 백업 파일입니다.")
                out.write(decryptor.update(block))
                remaining -= len(block)
            out.write(decryptor.finalize())
            out.flush()
            os.fsync(out.fileno())
    except BaseException as error:
        if created:
            Path(destination).unlink(missing_ok=True)
        if isinstance(error, InvalidTag):
            raise BackupError(
                "백업 인증에 실패했습니다. 키·손상 여부를 확인하세요."
            ) from None
        raise


def pg_environment(url, *, restore=False):
    parsed = make_url(url)
    if parsed.drivername not in {"postgresql+psycopg", "postgresql"}:
        raise BackupError("PostgreSQL 연결만 사용할 수 있습니다.")
    if not parsed.host or not parsed.database or not parsed.username:
        raise BackupError("명시적인 PostgreSQL 서버·계정·DB가 필요합니다.")
    environment = os.environ.copy()
    # Never inherit ambient libpq connection routing or authentication overrides.
    for name in list(environment):
        if name.startswith("PG"):
            environment.pop(name)
    container = os.environ.get(
        "FS_GW_RESTORE_PG_CONTAINER" if restore else "FS_GW_PG_CONTAINER"
    )
    environment.update(
        {
            "PGHOST": parsed.host,
            "PGPORT": str(5432 if container else parsed.port or 5432),
            "PGUSER": parsed.username,
            "PGPASSWORD": parsed.password or "",
            "PGDATABASE": parsed.database,
            "PGSSLMODE": str(parsed.query.get("sslmode", "prefer")),
        }
    )
    return environment, container


def pg_command(tool, url, *, restore=False):
    environment, container = pg_environment(url, restore=restore)
    if tool not in {"pg_dump", "pg_restore", "psql"}:
        raise BackupError("지원하지 않는 DB 도구입니다.")
    if container:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", container):
            raise BackupError("PG 도구 컨테이너 이름을 확인하세요.")
        command = ["docker", "exec", "-i"]
        for name in [
            "PGHOST",
            "PGPORT",
            "PGUSER",
            "PGPASSWORD",
            "PGDATABASE",
            "PGSSLMODE",
        ]:
            command += ["--env", name]
        command += [container, tool]
    else:
        directory = os.environ.get("FS_GW_PG_BIN")
        command = [str(Path(directory) / tool) if directory else tool]
    return command, environment


def run_pg(tool, url, args, *, input_file=None, output_file=None, restore=False):
    command, environment = pg_command(tool, url, restore=restore)
    try:
        result = subprocess.run(
            command + args,
            env=environment,
            stdin=input_file or subprocess.DEVNULL,
            stdout=output_file or subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=900,
            check=False,
        )
    except OSError, subprocess.TimeoutExpired:
        raise BackupError("PostgreSQL 도구 실행·시간 제한을 확인하세요.") from None
    if result.returncode:
        raise BackupError(
            "PostgreSQL 도구가 실패했습니다. 비공개 서버 진단을 확인하세요."
        )


def require_tool_version(tool, url, server_major, *, restore=False):
    command, environment = pg_command(tool, url, restore=restore)
    try:
        result = subprocess.run(
            command + ["--version"],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=True,
        )
        match = re.search(rb"PostgreSQL\) (\d+)\.", result.stdout)
        if not match or int(match[1]) != server_major:
            raise ValueError()
    except OSError, ValueError, subprocess.SubprocessError:
        raise BackupError(
            "서버와 같은 주 버전의 PostgreSQL 도구가 필요합니다."
        ) from None


def inventory(c):
    # Hash rows inside the DB and stream only hashes, never plaintext business rows.
    c.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    inspector = inspect(c)
    tables = {}
    schemas = [
        name
        for name in inspector.get_schema_names()
        if name != "information_schema" and not name.startswith("pg_")
    ]
    quote = c.dialect.identifier_preparer.quote
    for schema in sorted(schemas):
        for table in sorted(inspector.get_table_names(schema=schema)):
            digest = hashlib.sha256()
            count = 0
            query = f"SELECT encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex') AS h FROM {quote(schema)}.{quote(table)} t ORDER BY h"
            result = c.execute(text(query).execution_options(stream_results=True))
            for row in result:
                digest.update(row[0].encode())
                count += 1
            tables[schema + "." + table] = {"rows": count, "sha256": digest.hexdigest()}
    return tables


def database_identity(c):
    value = c.execute(
        text("SELECT system_identifier::text FROM pg_control_system()")
    ).scalar_one()
    database = c.execute(text("SELECT current_database()")).scalar_one()
    oid = c.execute(
        text("SELECT oid FROM pg_database WHERE datname=current_database()")
    ).scalar_one()
    return hashlib.sha256(json.dumps([value, database, oid]).encode()).hexdigest()


def fk_valid(c):
    # Also checks NOT VALID constraints: dump/restore may otherwise preserve them.
    return not c.execute(
        text(
            "SELECT count(*) FROM pg_constraint WHERE contype='f' AND NOT convalidated"
        )
    ).scalar_one()


def tool_database_identity(url, *, restore=False):
    """Ensure container/CLI routing points at the same physical source/target DB."""
    command, environment = pg_command("psql", url, restore=restore)
    query = "SELECT json_build_array((SELECT system_identifier::text FROM pg_control_system()),current_database(),(SELECT oid::bigint FROM pg_database WHERE datname=current_database()))"
    try:
        result = subprocess.run(
            command + ["-X", "--no-password", "-At", "--command=" + query],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=True,
        )
        value = json.loads(result.stdout)
        return hashlib.sha256(json.dumps(value).encode()).hexdigest()
    except OSError, ValueError, TypeError, subprocess.SubprocessError:
        raise BackupError(
            "PostgreSQL 도구와 DB 연결 대상 대조에 실패했습니다."
        ) from None

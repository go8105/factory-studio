from __future__ import annotations

from fs.common.db import get_engine
from fs.core.service import cleanup_expired_guests


def main() -> None:
    with get_engine().begin() as connection:
        count = cleanup_expired_guests(connection)
    print(f"cleaned_guest_workspaces={count}")


if __name__ == "__main__":
    main()

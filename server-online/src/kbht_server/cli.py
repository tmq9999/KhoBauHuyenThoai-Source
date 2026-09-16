from __future__ import annotations

import argparse

from kbht_server.db.migrations import apply_migrations, check_invariants
from kbht_server.db.session import database_url, open_engine
from sqlalchemy.schema import CreateSchema


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kbht-server")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("migrate", "check-invariants"):
        command = sub.add_parser(name)
        command.add_argument("--environment", choices=("test", "development"), required=True)
    args = parser.parse_args(argv)
    engine = open_engine(database_url(args.environment), schema="kbht_core")
    try:
        if args.command == "migrate":
            with engine.begin() as connection:
                connection.execute(CreateSchema("kbht_core", if_not_exists=True))
            print(apply_migrations(engine))
        else:
            print(check_invariants(engine))
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

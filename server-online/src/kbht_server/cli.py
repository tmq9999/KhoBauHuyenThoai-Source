from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from uuid import UUID
import uvicorn

from kbht_server.content.importer import store_source, load_source_row, prepare_draft, store_dependencies
from kbht_server.content.equipment_store import prepare_equipment_draft
from kbht_server.content.archive import store_acquisition

from kbht_server.db.migrations import apply_migrations, check_invariants
from kbht_server.db.session import database_url, open_engine
from sqlalchemy.schema import CreateSchema


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kbht-server")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("migrate", "check-invariants", "import-content", "import-dependencies", "prepare-equipment", "audit-acquisition", "read-content", "prepare-content"):
        command = sub.add_parser(name)
        command.add_argument("--environment", choices=("test", "development"), required=True)
        if name in ("import-content", "import-dependencies", "prepare-equipment", "audit-acquisition"):
            command.add_argument("--source", type=Path, required=True)
            command.add_argument("--source-sha256", required=True)
        if name in ("read-content", "prepare-content"):
            command.add_argument("--import-id", type=UUID, required=True)
        if name == "read-content":
            command.add_argument("--kind-id", type=int, required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--environment", choices=("test", "development"), required=True)
    serve.add_argument("--host", choices=("127.0.0.1", "::1"), default="127.0.0.1")
    serve.add_argument("--port", type=int, default=21001)
    inventory = sub.add_parser("serve-inventory")
    inventory.add_argument("--environment", choices=("test", "development"), required=True)
    inventory.add_argument("--host", choices=("127.0.0.1", "::1"), default="127.0.0.1")
    inventory.add_argument("--port", type=int, default=21002)
    bootstrap = sub.add_parser("serve-bootstrap")
    bootstrap.add_argument("--environment", choices=("test", "development"), required=True)
    bootstrap.add_argument("--host", choices=("127.0.0.1", "::1"), default="127.0.0.1")
    bootstrap.add_argument("--port", type=int, default=21003)
    bootstrap.add_argument("--inventory-url", default="ws://127.0.0.1:21002/inventory")
    native = sub.add_parser("serve-native")
    native.add_argument("--environment", choices=("test", "development"), required=True)
    native.add_argument("--host", choices=("127.0.0.1", "::1"), default="127.0.0.1")
    native.add_argument("--http-port", type=int, default=20003)
    native.add_argument("--gate-port", type=int, default=20100)
    native.add_argument("--connector-port", type=int, default=20101)
    native.add_argument("--manifest", type=Path)
    native.add_argument("--manifest-sha256")
    native.add_argument("--battle-artifact", type=Path)
    args = parser.parse_args(argv)
    if args.command == 'serve-bootstrap':
        from kbht_server.bootstrap import validate_inventory_url
        if not 1 <= args.port <= 65535:
            parser.error('bootstrap port must be between 1 and 65535')
        try:
            validate_inventory_url(args.inventory_url)
        except ValueError:
            parser.error('invalid loopback inventory URL')
    if args.command == 'serve-native':
        if bool(args.manifest) != bool(args.manifest_sha256):
            parser.error('manifest and manifest-sha256 must be supplied together')
        if args.manifest:
            from kbht_server.adapters.native_metadata import load_manifest
            try:
                load_manifest(args.manifest, args.manifest_sha256)
            except (OSError, ValueError):
                parser.error('invalid pinned native manifest')
            if args.host != '127.0.0.1' or 20001 in (args.http_port, args.gate_port, args.connector_port):
                parser.error('native metadata requires IPv4 loopback and distinct port20001')
        if any(type(port) is not int or not 1 <= port <= 65535 for port in
               (args.http_port, args.gate_port, args.connector_port)):
            parser.error('native ports must be between 1 and 65535')
        if len({args.http_port, args.gate_port, args.connector_port}) != 3:
            parser.error('native ports must be distinct')
    engine = open_engine(database_url(args.environment), schema="kbht_core")
    try:
        if args.command == 'serve-bootstrap':
            from kbht_server.adapters.bootstrap import create_bootstrap_app
            app = create_bootstrap_app(engine, inventory_url=args.inventory_url)
            uvicorn.run(app, host=args.host, port=args.port, log_level='warning',
                        access_log=False, proxy_headers=False)
            return 0
        if args.command == 'serve-native':
            from kbht_server.adapters.native_auth import create_native_auth_app
            from kbht_server.adapters.native_gateway import NativePomeloServer
            battle_engine = None
            if args.battle_artifact:
                from kbht_server.battles.engine import RecoveredBattleEngine, ARTIFACT_SHA256
                import hashlib
                try:
                    with args.battle_artifact.open('rb') as battle_file:
                        artifact_bytes = battle_file.read(600001)
                    if len(artifact_bytes)>600000 or hashlib.sha256(artifact_bytes).hexdigest()!=ARTIFACT_SHA256:
                        raise ValueError('battle artifact mismatch')
                except (OSError, ValueError):
                    parser.error('invalid pinned battle artifact')
                battle_engine = RecoveredBattleEngine(args.battle_artifact)

            async def run_native() -> None:
                import uvicorn
                http_server = uvicorn.Server(uvicorn.Config(
                    create_native_auth_app(engine), host=args.host, port=args.http_port,
                    log_level='warning', access_log=False, proxy_headers=False))
                gate = NativePomeloServer(engine, role='gate', host=args.host,
                    port=args.gate_port, connector_host=args.host,
                    connector_port=args.connector_port)
                connector = NativePomeloServer(engine, role='connector', host=args.host,
                    port=args.connector_port, battle_engine=battle_engine)
                servers = [http_server]
                if args.manifest:
                    from kbht_server.adapters.native_metadata import create_native_metadata_app
                    servers.append(uvicorn.Server(uvicorn.Config(
                        create_native_metadata_app(args.manifest, args.manifest_sha256),
                        host='127.0.0.1', port=20001, log_level='warning',
                        access_log=False, proxy_headers=False)))
                tasks = []
                try:
                    await connector.start()
                    await gate.start()
                    tasks = [asyncio.create_task(server.serve()) for server in servers]
                    done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        task.result()
                finally:
                    for server in servers:
                        server.should_exit = True
                    if tasks:
                        done, pending = await asyncio.wait(tasks, timeout=5)
                        for task in pending:
                            task.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)
                    await gate.close()
                    await connector.close()

            try:
                asyncio.run(run_native())
            except KeyboardInterrupt:
                pass
            return 0
        if args.command == "serve-inventory":
            from kbht_server.adapters.pomelo_transport import PomeloInventoryServer

            async def run_inventory() -> None:
                server = PomeloInventoryServer(engine, host=args.host, port=args.port)
                await server.start()
                try:
                    await asyncio.Event().wait()
                finally:
                    await server.close()

            try:
                asyncio.run(run_inventory())
            except KeyboardInterrupt:
                pass
            return 0
        if args.command == "serve":
            from kbht_server.adapters.commands import CommandAdapter
            from kbht_server.adapters.http import create_app
            from kbht_server.db.uow import CommandExecutor
            from kbht_server.auth import SessionService
            app = create_app(CommandAdapter(CommandExecutor(engine, {})), authenticate=SessionService(engine).resolve)
            uvicorn.run(app, host=args.host, port=args.port, log_level="info")
            return 0
        if args.command == "migrate":
            with engine.begin() as connection:
                connection.execute(CreateSchema("kbht_core", if_not_exists=True))
            print(apply_migrations(engine))
        elif args.command == "import-content":
            print(json.dumps(store_source(engine, args.source, args.source_sha256), default=str))
        elif args.command == "import-dependencies":
            print(json.dumps(store_dependencies(engine, args.source, args.source_sha256), default=str))
        elif args.command == "prepare-equipment":
            print(json.dumps(prepare_equipment_draft(engine, args.source, args.source_sha256), default=str))
        elif args.command == "audit-acquisition":
            print(json.dumps(store_acquisition(engine, args.source, args.source_sha256), default=str))
        elif args.command == "read-content":
            print(json.dumps(load_source_row(engine, args.import_id, args.kind_id), ensure_ascii=True))
        elif args.command == "prepare-content":
            print(json.dumps(prepare_draft(engine, args.import_id), default=str))
        else:
            print(check_invariants(engine))
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

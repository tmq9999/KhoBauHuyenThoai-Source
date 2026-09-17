"""Disposable child process for fixed-box transaction loss tests only."""
import os
from pathlib import Path
import re
import sys
from uuid import UUID

sys.path.insert(0,str(Path(__file__).parent))
from sqlalchemy import text
from kbht_server.contracts import GameCommand
from kbht_server.db.session import database_url,open_engine
from kbht_server.db.uow import CommandExecutor
from kbht_server.economy.boxes import use_fixed_box
from pg_lab import ACCOUNT_IDS,CONTENT_ID


def main():
    schema,phase,command_id,inventory_id,version=sys.argv[1:]
    if not re.fullmatch(r'kbht_t_[0-9a-f]{32}',schema) or phase not in ('before-commit','after-commit'):
        raise ValueError('disposable test schema and phase required')
    engine=open_engine(database_url('test'),schema=schema)
    with engine.connect() as connection:
        if connection.execute(text('SELECT current_database()')).scalar_one()!='kbht_test':
            raise ValueError('test database required')
    cmd=GameCommand(UUID(command_id),ACCOUNT_IDS[10001],10001,1,'inventory.useFixedBox',
                    int(version),CONTENT_ID,{'inventory_id':int(inventory_id),'quantity':1})
    def crash_handler(work,payload):
        result=use_fixed_box(work,payload)
        if phase=='before-commit':
            os._exit(81)
        return result
    CommandExecutor(engine,{cmd.route:crash_handler}).execute(cmd)
    os._exit(82)


if __name__=='__main__':
    main()

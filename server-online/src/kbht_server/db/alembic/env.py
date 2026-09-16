from alembic import context

# The CLI validates the target and provides one transaction; no DSNs in config.
connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("Use kbht-server migrate with an explicit lab environment")
context.configure(connection=connection)
with context.begin_transaction():
    context.run_migrations()

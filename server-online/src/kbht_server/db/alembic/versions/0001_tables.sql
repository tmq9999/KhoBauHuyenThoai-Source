-- Frozen PostgreSQL 0001 table DDL, generated from the initial metadata.
CREATE TABLE accounts (
	id UUID NOT NULL,
	normalized_login VARCHAR(128) NOT NULL,
	password_hash TEXT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (normalized_login)
);

CREATE TABLE content_versions (
	id UUID NOT NULL,
	source_sha256 VARCHAR(64) NOT NULL,
	rules_sha256 VARCHAR(64) NOT NULL,
	status VARCHAR(16) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_content_versions_status CHECK (status IN ('DRAFT', 'VALIDATED', 'PUBLISHED', 'RETIRED'))
);

CREATE TABLE game_servers (
	id SERIAL NOT NULL,
	name VARCHAR(64) NOT NULL,
	status VARCHAR(16) DEFAULT 'MAINTENANCE' NOT NULL,
	active_content_version_id UUID,
	business_timezone VARCHAR(64) DEFAULT 'Asia/Ho_Chi_Minh' NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_game_servers_status CHECK (status IN ('MAINTENANCE', 'OPEN', 'CLOSED')),
	UNIQUE (name),
	FOREIGN KEY(active_content_version_id) REFERENCES content_versions (id)
);

CREATE TABLE players (
	id BIGSERIAL NOT NULL,
	account_id UUID NOT NULL,
	server_id INTEGER NOT NULL,
	name VARCHAR(64) NOT NULL,
	version INTEGER DEFAULT '0' NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_players_account_server UNIQUE (account_id, server_id),
	CONSTRAINT ck_players_version_nonnegative CHECK (version >= 0),
	FOREIGN KEY(account_id) REFERENCES accounts (id) ON DELETE CASCADE,
	FOREIGN KEY(server_id) REFERENCES game_servers (id)
);

CREATE TABLE command_receipts (
	player_id BIGINT NOT NULL,
	command_id UUID NOT NULL,
	route VARCHAR(160) NOT NULL,
	payload_hash VARCHAR(64) NOT NULL,
	result_json JSONB NOT NULL,
	aggregate_version INTEGER NOT NULL,
	status VARCHAR(16) NOT NULL,
	content_version_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (player_id, command_id),
	CONSTRAINT ck_command_receipts_status CHECK (status IN ('COMMITTED')),
	FOREIGN KEY(player_id) REFERENCES players (id) ON DELETE CASCADE,
	FOREIGN KEY(content_version_id) REFERENCES content_versions (id)
);

CREATE TABLE ledger_transactions (
	id UUID NOT NULL,
	player_id BIGINT NOT NULL,
	command_id UUID NOT NULL,
	reason VARCHAR(160) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_ledger_transactions_command UNIQUE (player_id, command_id),
	FOREIGN KEY(player_id) REFERENCES players (id) ON DELETE CASCADE
);

CREATE TABLE outbox_events (
	id UUID NOT NULL,
	player_id BIGINT NOT NULL,
	command_id UUID NOT NULL,
	event_type VARCHAR(160) NOT NULL,
	body JSONB NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(player_id) REFERENCES players (id) ON DELETE CASCADE
);

CREATE TABLE wallets (
	player_id BIGINT NOT NULL,
	currency VARCHAR(32) NOT NULL,
	balance BIGINT DEFAULT '0' NOT NULL,
	version INTEGER DEFAULT '0' NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (player_id, currency),
	CONSTRAINT ck_wallets_balance_nonnegative CHECK (balance BETWEEN 0 AND 9007199254740991),
	CONSTRAINT ck_wallets_version_nonnegative CHECK (version >= 0),
	FOREIGN KEY(player_id) REFERENCES players (id) ON DELETE CASCADE
);

CREATE TABLE ledger_postings (
	transaction_id UUID NOT NULL,
	line_no INTEGER NOT NULL,
	currency VARCHAR(32) NOT NULL,
	account_key VARCHAR(80) NOT NULL,
	delta BIGINT NOT NULL,
	PRIMARY KEY (transaction_id, line_no),
	FOREIGN KEY(transaction_id) REFERENCES ledger_transactions (id)
);

CREATE TABLE wallet_ledger (
	id UUID NOT NULL,
	player_id BIGINT NOT NULL,
	currency VARCHAR(32) NOT NULL,
	delta BIGINT NOT NULL,
	balance_after BIGINT NOT NULL,
	reason VARCHAR(160) NOT NULL,
	command_id UUID NOT NULL,
	transaction_id UUID NOT NULL,
	line_no INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_wallet_ledger_command_reason UNIQUE (player_id, currency, command_id, reason),
	CONSTRAINT uq_wallet_ledger_transaction_line UNIQUE (transaction_id, line_no),
	FOREIGN KEY(transaction_id, line_no) REFERENCES ledger_postings (transaction_id, line_no),
	CONSTRAINT ck_wallet_ledger_balance_nonnegative CHECK (balance_after >= 0),
	FOREIGN KEY(player_id) REFERENCES players (id) ON DELETE CASCADE,
	FOREIGN KEY(transaction_id) REFERENCES ledger_transactions (id) ON DELETE CASCADE
);

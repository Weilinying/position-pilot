"""新增持续用户意图，保留账本和 Conversation 数据。"""

from alembic import op

revision = "20261004_0011"
down_revision = "20260922_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """只新增表及复合来源约束，不迁移金融事实。"""
    op.execute("""
        ALTER TABLE conversation_messages ADD CONSTRAINT uq_conversation_messages_id_owner
        UNIQUE (id, thread_id, account_id)
        """)
    op.execute("""
        CREATE TABLE strategy_identities (
                id UUID NOT NULL,
                account_id UUID NOT NULL,
                scope_key VARCHAR(128) NOT NULL,
                ticker VARCHAR(32) NOT NULL,
                position_type VARCHAR(16) NOT NULL,
                kind VARCHAR(64) NOT NULL,
                PRIMARY KEY (id),
                CONSTRAINT uq_strategy_identity_scope UNIQUE (account_id, scope_key, kind),
                CONSTRAINT uq_strategy_identity_owner UNIQUE (id, account_id, scope_key, kind),
                CONSTRAINT ck_strategy_scope_type CHECK (position_type IN
        ('LONG_TERM','SWING')),
                CONSTRAINT ck_strategy_scope_key CHECK (scope_key = ticker || ':' ||
        position_type),
                CONSTRAINT ck_strategy_kind CHECK (kind IN
        ('POSITION_PLAN_V1','INVESTMENT_THESIS_V1','HOLDING_HORIZON_V1')),
                FOREIGN KEY(account_id) REFERENCES accounts (id)
        )
        """)
    op.execute("""
        CREATE TABLE strategy_candidates (
                id UUID NOT NULL,
                account_id UUID NOT NULL,
                thread_id UUID NOT NULL,
                strategy_id UUID NOT NULL,
                scope_key VARCHAR(128) NOT NULL,
                kind VARCHAR(64) NOT NULL,
                status VARCHAR(16) NOT NULL,
                source_user_message_id UUID NOT NULL,
                assistant_message_id UUID NOT NULL,
                proposal_request_id UUID NOT NULL,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                record JSON NOT NULL,
                PRIMARY KEY (id),
                CONSTRAINT fk_candidate_scope FOREIGN KEY(strategy_id, account_id, scope_key,
        kind) REFERENCES strategy_identities (id, account_id, scope_key, kind),
                CONSTRAINT fk_candidate_thread_owner FOREIGN KEY(thread_id, account_id)
        REFERENCES conversation_threads (id, account_id),
                CONSTRAINT fk_candidate_user_owner FOREIGN KEY(source_user_message_id,
        thread_id, account_id) REFERENCES conversation_messages (id, thread_id, account_id),
                CONSTRAINT fk_candidate_assistant_owner FOREIGN KEY(assistant_message_id,
        thread_id, account_id) REFERENCES conversation_messages (id, thread_id, account_id),
                CONSTRAINT uq_candidate_identity_owner UNIQUE (id, account_id, strategy_id),
                CONSTRAINT uq_candidate_assistant UNIQUE (assistant_message_id),
                CONSTRAINT uq_candidate_proposal_request UNIQUE (account_id,
        proposal_request_id),
                CONSTRAINT ck_candidate_status CHECK (status IN
        ('PENDING','CONFIRMED','CANCELLED','EXPIRED','STALE'))
        )
        """)
    op.execute("""
        CREATE UNIQUE INDEX uq_candidate_pending_scope ON strategy_candidates (account_id,
        scope_key, kind) WHERE status = 'PENDING'
        """)
    op.execute("""
        CREATE TABLE confirmed_strategy_versions (
                id UUID NOT NULL,
                strategy_id UUID NOT NULL,
                account_id UUID NOT NULL,
                scope_key VARCHAR(128) NOT NULL,
                kind VARCHAR(64) NOT NULL,
                version INTEGER NOT NULL,
                status VARCHAR(16) NOT NULL,
                source_candidate_id UUID NOT NULL,
                confirmation_request_id UUID NOT NULL,
                record JSON NOT NULL,
                PRIMARY KEY (id),
                CONSTRAINT fk_version_scope FOREIGN KEY(strategy_id, account_id, scope_key,
        kind) REFERENCES strategy_identities (id, account_id, scope_key, kind),
                CONSTRAINT fk_version_candidate_owner FOREIGN KEY(source_candidate_id,
        account_id, strategy_id) REFERENCES strategy_candidates (id, account_id, strategy_id),
                CONSTRAINT uq_strategy_version UNIQUE (strategy_id, version),
                CONSTRAINT uq_strategy_confirmation_request UNIQUE (account_id,
        confirmation_request_id),
                CONSTRAINT uq_strategy_confirmed_candidate UNIQUE (source_candidate_id),
                CONSTRAINT ck_strategy_version_positive CHECK (version > 0),
                CONSTRAINT ck_strategy_version_status CHECK (status IN
        ('ACTIVE','SUPERSEDED','INVALIDATED'))
        )
        """)
    op.execute("""
        CREATE UNIQUE INDEX uq_strategy_active_scope ON confirmed_strategy_versions (account_id,
        scope_key, kind) WHERE status = 'ACTIVE'
        """)


def downgrade() -> None:
    """仅供空测试库回退；正式回滚保留意图数据。"""
    op.drop_table("confirmed_strategy_versions")
    op.drop_table("strategy_candidates")
    op.drop_table("strategy_identities")
    op.drop_constraint("uq_conversation_messages_id_owner", "conversation_messages", type_="unique")

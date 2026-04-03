from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ontology_edge_history (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            edge_type TEXT NOT NULL,
            source_entity_id TEXT NOT NULL,
            target_entity_id TEXT NOT NULL,
            properties JSONB NOT NULL DEFAULT '{}',
            valid_from TIMESTAMPTZ NOT NULL,
            valid_to TIMESTAMPTZ,
            observed_source TEXT,
            scenario_id TEXT REFERENCES scenarios(id),
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_edge_history_temporal "
        "ON ontology_edge_history (edge_type, valid_from, valid_to);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_edge_history_source "
        "ON ontology_edge_history (source_entity_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_edge_history_target "
        "ON ontology_edge_history (target_entity_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_edge_history_scenario "
        "ON ontology_edge_history (scenario_id);"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS simulation_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            scenario_id TEXT NOT NULL REFERENCES scenarios(id),
            event_type TEXT NOT NULL,
            payload JSONB NOT NULL,
            sequence_num BIGSERIAL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_sim_events_scenario_seq "
        "ON simulation_events (scenario_id, sequence_num);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS simulation_events CASCADE;")
    op.execute("DROP TABLE IF EXISTS ontology_edge_history CASCADE;")

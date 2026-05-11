-- ============================================================
-- NOTIFICATION CHANNELS & HISTORY
-- Stores runtime-configurable notification destinations and
-- an audit trail of every dispatched notification.
-- ============================================================

-- ── Notification channels (runtime-configurable) ──────────────────────────
CREATE TABLE notification_channels (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_type TEXT    NOT NULL,              -- 'telegram' | 'email' | 'webhook'
    channel_name TEXT    NOT NULL,              -- human-readable label
    -- channel_type-specific config stored as JSON:
    --   telegram : {"chat_id": "-100123456789"}
    --   email    : {"address": "ops@example.com"}
    --   webhook  : {"url": "https://...", "secret": "..."}
    config       JSONB   NOT NULL DEFAULT '{}',
    -- Routing rules
    min_severity TEXT    NOT NULL DEFAULT 'high',   -- low/medium/high/critical
    alert_types  TEXT[]  NOT NULL DEFAULT '{}',      -- empty = all types
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notif_channels_active
    ON notification_channels(channel_type, is_active)
    WHERE is_active = TRUE;

-- ── Notification history (audit + dedup) ──────────────────────────────────
CREATE TABLE notification_history (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_id       UUID REFERENCES alerts(id) ON DELETE CASCADE,
    channel_id     UUID REFERENCES notification_channels(id) ON DELETE SET NULL,
    channel_type   TEXT NOT NULL,
    channel_target TEXT,                   -- chat_id or email address
    status         TEXT NOT NULL DEFAULT 'sent',   -- sent | failed | suppressed
    error_message  TEXT,
    sent_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notif_history_alert
    ON notification_history(alert_id, channel_type);
CREATE INDEX idx_notif_history_sent
    ON notification_history(sent_at DESC);

-- Prune history older than 90 days
CREATE OR REPLACE FUNCTION prune_notification_history()
RETURNS VOID AS $$
BEGIN
    DELETE FROM notification_history WHERE sent_at < NOW() - INTERVAL '90 days';
END;
$$ LANGUAGE plpgsql;

-- ── Updated-at trigger ─────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_notif_channels_updated_at
    BEFORE UPDATE ON notification_channels
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ── RLS (service-role bypasses these) ─────────────────────────────────────
ALTER TABLE notification_channels  ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_history   ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_channels"
    ON notification_channels FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "service_role_all_history"
    ON notification_history FOR ALL
    USING (auth.role() = 'service_role');

-- ── Seed: example placeholder channels (inactive until tokens added) ──────
INSERT INTO notification_channels (channel_type, channel_name, config, min_severity, is_active)
VALUES
    ('telegram', 'Ops Channel',     '{"chat_id": ""}', 'high',   FALSE),
    ('telegram', 'Critical-Only',   '{"chat_id": ""}', 'critical', FALSE),
    ('email',    'Ops Team',        '{"address": ""}', 'medium', FALSE);

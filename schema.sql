-- schema.sql

-- Enable the UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users Table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    telegram_id BIGINT UNIQUE,
    bot_state TEXT DEFAULT 'HANDSHAKE', -- States: HANDSHAKE, ONBOARDING, ACTIVE
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- User Configurations (Brand DNA)
CREATE TABLE user_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    business_name TEXT,
    business_address TEXT,
    contact_details TEXT,
    bank_info TEXT,
    vat_tax_status TEXT,
    currency TEXT DEFAULT 'USD',
    calculation_methods JSONB,
    layout_preferences JSONB,
    preferred_format TEXT DEFAULT 'docx', -- Preferred output: docx, xlsx, pdf
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Documents (Generated Quotes/Invoices)
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    customer_name TEXT,
    customer_address TEXT,
    line_items JSONB,
    subtotal NUMERIC,
    tax_amount NUMERIC,
    discount NUMERIC,
    total NUMERIC,
    file_url TEXT, -- Link to file in Supabase Storage
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Row Level Security (service role bypasses RLS; blocks public/anon access)
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- MIGRATION: Run these statements in Supabase SQL editor
-- ============================================================

-- Add subscription fields to users
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_tier TEXT DEFAULT 'free';
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT;

-- Subscriptions table — tracks active Stripe subscriptions
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    stripe_subscription_id TEXT UNIQUE,
    stripe_customer_id TEXT,
    plan_tier TEXT DEFAULT 'free',       -- 'free' | 'premium'
    status TEXT DEFAULT 'active',        -- 'active' | 'canceled' | 'past_due' | 'unpaid'
    current_period_start TIMESTAMP WITH TIME ZONE,
    current_period_end TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS current_period_start TIMESTAMP WITH TIME ZONE;

ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

-- Feedback Table (stores user feedback from /feedback bot command)
CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    telegram_id BIGINT,
    email TEXT,
    message TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- MIGRATION: Pending quote state (survives restarts, enables multi-worker)
-- Run in Supabase SQL editor
-- ============================================================

ALTER TABLE users ADD COLUMN IF NOT EXISTS pending_quote JSONB DEFAULT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS pending_brand_dna JSONB DEFAULT NULL;

-- Fix bot_state comment to document all states
COMMENT ON COLUMN users.bot_state IS 'States: HANDSHAKE | ONBOARDING | AWAITING_FORMAT | ACTIVE | AWAITING_CONFIRMATION';

-- ============================================================
-- MIGRATION: Login tokens table (replaces in-memory dict, works across workers)
-- Run in Supabase SQL editor
-- ============================================================

CREATE TABLE IF NOT EXISTS login_tokens (
    token      TEXT PRIMARY KEY,
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

ALTER TABLE login_tokens ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- MIGRATION: pg_cron cleanup for expired login tokens
-- Run in Supabase SQL editor (pg_cron is enabled by default on Supabase)
-- ============================================================

SELECT cron.schedule(
    'cleanup-expired-login-tokens',
    '*/15 * * * *',
    $$DELETE FROM login_tokens WHERE expires_at < now()$$
);

-- ============================================================
-- MIGRATION: Atomic quota reservation function
-- Atomically checks monthly quota and inserts a placeholder document
-- row in a single transaction, preventing race conditions when two
-- requests arrive simultaneously near the quota limit.
-- Returns the new document UUID if a slot was available, NULL if quota
-- is already reached.
-- ============================================================

CREATE OR REPLACE FUNCTION reserve_quota_slot(
    p_user_id     UUID,
    p_billing_start TIMESTAMPTZ,
    p_limit       INT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_count  INT;
    v_doc_id UUID;
BEGIN
    -- Per-user advisory lock scoped to this transaction.
    -- Two concurrent calls for the same user will queue here rather than
    -- both reading the same count and both deciding they're under the limit.
    PERFORM pg_advisory_xact_lock(('x' || md5(p_user_id::text))::bit(64)::bigint);

    SELECT COUNT(*) INTO v_count
    FROM documents
    WHERE user_id = p_user_id
      AND created_at >= p_billing_start;

    IF v_count >= p_limit THEN
        RETURN NULL;
    END IF;

    -- Insert a placeholder row to claim the slot; the application fills in
    -- the actual quote data once the document has been generated and sent.
    INSERT INTO documents (user_id)
    VALUES (p_user_id)
    RETURNING id INTO v_doc_id;

    RETURN v_doc_id;
END;
$$;

-- ============================================================
-- MIGRATION: Supabase Storage bucket for onboarding samples
-- Run these steps in the Supabase dashboard (Storage section):
--   1. Create a new bucket named "onboarding" (private, no public access)
--   2. Optionally set a lifecycle rule to auto-delete files older than 7 days
-- No SQL required — bucket creation is done via the dashboard or Management API.
-- ============================================================

-- ============================================================
-- MIGRATION: docxtpl quote template per user
-- Run in Supabase SQL editor:
-- ============================================================

ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS template_docx_path TEXT;

-- Also create a new private Storage bucket named "quote-templates" in the
-- Supabase dashboard (Storage section). No public access needed.

-- ============================================================
-- MIGRATION: brand color columns for document theming
-- Run in Supabase SQL editor:
-- ============================================================

ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS primary_color_hex TEXT;
ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS secondary_color_hex TEXT;

-- ============================================================
-- MIGRATION: logo storage for scratch document generation
-- Run in Supabase SQL editor:
-- ============================================================

ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS logo_path TEXT;

-- ============================================================
-- MIGRATION: Promo code system
-- Run in Supabase SQL editor
-- ============================================================

CREATE TABLE IF NOT EXISTS promo_codes (
    code           TEXT PRIMARY KEY,
    benefit_type   TEXT NOT NULL,        -- 'extra_quotes' | 'premium_months'
    benefit_value  INT  NOT NULL,        -- e.g. 10 (quote limit) or 3 (months of premium)
    max_uses       INT,                  -- NULL = unlimited
    uses_count     INT  NOT NULL DEFAULT 0,
    is_active      BOOLEAN NOT NULL DEFAULT true,
    expires_at     TIMESTAMP WITH TIME ZONE
);

ALTER TABLE promo_codes ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS user_promo_redemptions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code         TEXT NOT NULL REFERENCES promo_codes(code),
    redeemed_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT timezone('utc', now()),
    expires_at   TIMESTAMP WITH TIME ZONE NOT NULL,
    benefit_type TEXT NOT NULL,
    benefit_value INT NOT NULL,
    UNIQUE(user_id, code)
);

ALTER TABLE user_promo_redemptions ENABLE ROW LEVEL SECURITY;

-- Seed the initial promo codes
INSERT INTO promo_codes (code, benefit_type, benefit_value, max_uses)
VALUES
    ('first50',      'extra_quotes',   10,   50),
    ('materate123',  'premium_months',  3, NULL),
    ('LAUNCH_BONUS', 'extra_quotes',   10, NULL)
ON CONFLICT (code) DO NOTHING;

-- ============================================================
-- MIGRATION: Template-based onboarding redesign
-- Run in Supabase SQL editor
-- ============================================================

-- Store the original blank template (before Jinja2 mapping)
ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS blank_template_path TEXT;

-- ============================================================
-- MIGRATION: Track scheduled cancellations from Stripe
-- Run in Supabase SQL editor
-- ============================================================

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS cancel_at_period_end BOOLEAN NOT NULL DEFAULT false;

-- Document the new intermediate onboarding states
COMMENT ON COLUMN users.bot_state IS
'States: HANDSHAKE | ONBOARDING | ONBOARDING_CURRENCY | ONBOARDING_TAX | AWAITING_FORMAT | ACTIVE | AWAITING_CONFIRMATION';

-- ============================================================
-- MIGRATION: XLSX template support — auto-match output format to uploaded template
-- Run in Supabase SQL editor
-- ============================================================

ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS template_xlsx_path TEXT;
ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS xlsx_field_mapping JSONB;

COMMENT ON COLUMN users.bot_state IS
'States: HANDSHAKE | ONBOARDING | ONBOARDING_CURRENCY | ONBOARDING_TAX | AWAITING_FORMAT (legacy) | ACTIVE | AWAITING_CONFIRMATION';

-- ============================================================
-- MIGRATION: Custom template fields — stores AI-discovered custom fields per template
-- Run in Supabase SQL editor
-- ============================================================

ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS custom_template_fields JSONB;

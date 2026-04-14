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
    current_period_end TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

-- Feedback Table (stores user feedback from /feedback bot command)
CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    telegram_id BIGINT,
    message TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;

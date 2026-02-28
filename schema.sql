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

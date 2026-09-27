-- Tables that predate Flyway: public.users (formerly created by the app's create_all)
-- and the module catalogue (created outside this repository).
--
-- The remote database already has these tables and is baselined at version 3, so this
-- file never runs there. It only builds fresh local and CI databases. It is reconstructed
-- from app/models/; if it drifts from remote, align it with
--   pg_dump --schema-only -t public.users -t modules.modules_master -t modules.sub_modules_master
--
-- Plain CREATE TABLE (no IF NOT EXISTS) on purpose: running it against a populated
-- database fails loudly instead of silently skipping.
CREATE TABLE public.users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    username VARCHAR(64) NOT NULL,
    hashed_password VARCHAR(255),
    google_sub VARCHAR(64),
    full_name VARCHAR(128),
    date_of_birth DATE,
    gender VARCHAR(32),
    bio TEXT,
    phone_country_code VARCHAR(8),
    phone_number VARCHAR(32),
    avatar_url VARCHAR(512),
    onboarding_completed BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ix_users_email ON public.users(email);
CREATE UNIQUE INDEX ix_users_username ON public.users(username);
CREATE UNIQUE INDEX ix_users_google_sub ON public.users(google_sub);

CREATE SCHEMA IF NOT EXISTS modules;
CREATE TABLE modules.modules_master (
    module_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_name VARCHAR(255) NOT NULL,
    module_description TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE modules.sub_modules_master (
    sub_module_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sub_module_name VARCHAR(255) NOT NULL,
    sub_module_description TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Carvion Motors dealership profiles: PostgreSQL migration reference.
-- Apply through a reviewed Alembic revision before deploying this feature.
-- This file is not executed automatically.
CREATE TABLE IF NOT EXISTS dealerships (
    id SERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
    name VARCHAR(120) NOT NULL,
    slug VARCHAR(150) NOT NULL UNIQUE,
    location VARCHAR(160) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    description TEXT,
    logo_url VARCHAR(500),
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_dealerships_owner_id ON dealerships(owner_id);
CREATE INDEX IF NOT EXISTS ix_dealerships_slug ON dealerships(slug);

-- Apply only after backing up the production PostgreSQL database.
-- This is a one-time, additive migration for the managed seller integration.
-- Existing cars retain their seller_id and seller_profile_id is NULL.
BEGIN;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS seller_profile_id INTEGER;
CREATE INDEX IF NOT EXISTS ix_cars_seller_profile_id ON cars (seller_profile_id);
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_cars_seller_profile_id'
    ) THEN
        ALTER TABLE cars ADD CONSTRAINT fk_cars_seller_profile_id
        FOREIGN KEY (seller_profile_id) REFERENCES seller_profiles(id);
    END IF;
END $$;
COMMIT;

-- Add 'draft' to job_status_enum so JD-upload draft jobs can be created.
-- Run this once against your PostgreSQL database, e.g.:
--   psql -U your_user -d your_db -f migrations/add_job_status_draft.sql

ALTER TYPE job_status_enum ADD VALUE IF NOT EXISTS 'draft';

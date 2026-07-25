-- SpecIndex Schema V2 — additive migration for warehouse/API interoperability.
-- See docs/DATA_SCHEMA_V2.md for full rationale. Idempotent — safe to re-run.
--
-- Nothing here drops or renames an existing column. api/main.py continues to
-- work unmodified against the v1 columns after this runs.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Numeric surrogate key
-- ---------------------------------------------------------------------------

ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS project_sk BIGINT GENERATED ALWAYS AS IDENTITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'projects_sk_pkey'
  ) THEN
    ALTER TABLE projects DROP CONSTRAINT IF EXISTS projects_pkey;
    ALTER TABLE projects ADD CONSTRAINT projects_sk_pkey PRIMARY KEY (project_sk);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'projects_id_unique'
  ) THEN
    ALTER TABLE projects ADD CONSTRAINT projects_id_unique UNIQUE (project_id);
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 2. Numeric + descriptive pairing for status / project_type
-- ---------------------------------------------------------------------------

ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS status_code SMALLINT,
  ADD COLUMN IF NOT EXISTS project_type_code SMALLINT;

UPDATE projects SET status_code = CASE status
  WHEN 'planning'            THEN 1
  WHEN 'design'               THEN 2
  WHEN 'permitting'           THEN 3
  WHEN 'bidding'               THEN 4
  WHEN 'under_construction'   THEN 5
  WHEN 'completed'             THEN 6
  ELSE NULL
END
WHERE status_code IS NULL;

UPDATE projects p SET project_type_code = sub.code
FROM (
  SELECT project_type, DENSE_RANK() OVER (ORDER BY project_type) AS code
  FROM (SELECT DISTINCT project_type FROM projects WHERE project_type IS NOT NULL) t
) sub
WHERE p.project_type = sub.project_type AND p.project_type_code IS NULL;

-- ---------------------------------------------------------------------------
-- 3. Geographic reference (verified public FIPS data only — no fabrication)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dim_state (
  state       CHAR(2) PRIMARY KEY,
  state_fips  CHAR(2) NOT NULL,
  state_name  TEXT NOT NULL
);

INSERT INTO dim_state (state, state_fips, state_name) VALUES
  ('AL','01','Alabama'),('AK','02','Alaska'),('AZ','04','Arizona'),('AR','05','Arkansas'),
  ('CA','06','California'),('CO','08','Colorado'),('CT','09','Connecticut'),('DE','10','Delaware'),
  ('DC','11','District of Columbia'),('FL','12','Florida'),('GA','13','Georgia'),('HI','15','Hawaii'),
  ('ID','16','Idaho'),('IL','17','Illinois'),('IN','18','Indiana'),('IA','19','Iowa'),
  ('KS','20','Kansas'),('KY','21','Kentucky'),('LA','22','Louisiana'),('ME','23','Maine'),
  ('MD','24','Maryland'),('MA','25','Massachusetts'),('MI','26','Michigan'),('MN','27','Minnesota'),
  ('MS','28','Mississippi'),('MO','29','Missouri'),('MT','30','Montana'),('NE','31','Nebraska'),
  ('NV','32','Nevada'),('NH','33','New Hampshire'),('NJ','34','New Jersey'),('NM','35','New Mexico'),
  ('NY','36','New York'),('NC','37','North Carolina'),('ND','38','North Dakota'),('OH','39','Ohio'),
  ('OK','40','Oklahoma'),('OR','41','Oregon'),('PA','42','Pennsylvania'),('RI','44','Rhode Island'),
  ('SC','45','South Carolina'),('SD','46','South Dakota'),('TN','47','Tennessee'),('TX','48','Texas'),
  ('UT','49','Utah'),('VT','50','Vermont'),('VA','51','Virginia'),('WA','53','Washington'),
  ('WV','54','West Virginia'),('WI','55','Wisconsin'),('WY','56','Wyoming')
ON CONFLICT (state) DO NOTHING;

ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS state_fips  CHAR(2),
  ADD COLUMN IF NOT EXISTS county_fips CHAR(5),   -- left NULL: needs verified Census crosswalk, see docs/DATA_SCHEMA_V2.md
  ADD COLUMN IF NOT EXISTS cbsa_code   CHAR(5),   -- left NULL: same reason
  ADD COLUMN IF NOT EXISTS latitude    NUMERIC(9,6), -- left NULL: needs real geocoding
  ADD COLUMN IF NOT EXISTS longitude   NUMERIC(9,6); -- left NULL: needs real geocoding

UPDATE projects p SET state_fips = d.state_fips
FROM dim_state d
WHERE p.state = d.state AND p.state_fips IS NULL;

-- ---------------------------------------------------------------------------
-- 4. External interoperability
-- ---------------------------------------------------------------------------

ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS external_ids   JSONB NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS record_type    TEXT,
  ADD COLUMN IF NOT EXISTS value_currency CHAR(3) NOT NULL DEFAULT 'USD';

UPDATE projects
SET record_type = CASE WHEN project_id ~ '^[a-z]{2}-dri-' THEN 'dri_filing' ELSE 'permit_or_press' END
WHERE record_type IS NULL;

-- DRI filing number, parsed from ids like "ga-dri-4802-..."
UPDATE projects
SET external_ids = external_ids || jsonb_build_object('ga_dri_number', (regexp_match(project_id, '^[a-z]{2}-dri-(\d+)-'))[1])
WHERE project_id ~ '^[a-z]{2}-dri-\d+-'
  AND NOT (external_ids ? 'ga_dri_number');

-- County/city permit code, parsed from trailing slug segment like "...-bc250259"
UPDATE projects
SET external_ids = external_ids || jsonb_build_object(
      'county_permit',
      upper((regexp_match(project_id, '-([a-z]{1,4}[0-9]{5,7})$'))[1])
    )
WHERE project_id ~ '-[a-z]{1,4}[0-9]{5,7}$'
  AND NOT (external_ids ? 'county_permit');

-- Explicit "-permit-<digits>" pattern (e.g. Chicago open-data ids)
UPDATE projects
SET external_ids = external_ids || jsonb_build_object(
      'county_permit',
      (regexp_match(project_id, '-permit-([0-9]+)$'))[1]
    )
WHERE project_id ~ '-permit-[0-9]+$'
  AND NOT (external_ids ? 'county_permit');

-- ---------------------------------------------------------------------------
-- 5. CSI MasterFormat division codes — schema slot only, populated by
--    scripts/extract-spec-book.py once spec book PDFs are sourced per project.
-- ---------------------------------------------------------------------------

ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS csi_division_codes SMALLINT[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS csi_divisions       JSONB NOT NULL DEFAULT '[]';

-- ---------------------------------------------------------------------------
-- 6. Warehouse/versioning fields
-- ---------------------------------------------------------------------------

ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS first_seen_at   TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS last_updated_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS data_confidence TEXT NOT NULL DEFAULT 'unverified';

UPDATE projects
SET first_seen_at = loaded_at, last_updated_at = loaded_at
WHERE first_seen_at IS NULL;

-- ---------------------------------------------------------------------------
-- 7. Dedup/rollup slot — left NULL for all rows, needs human-reviewed pass
--    (see docs/DATA_SCHEMA_V2.md section 5, the "Brookside Reserve" example)
-- ---------------------------------------------------------------------------

ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS parent_project_id TEXT REFERENCES projects(project_id);

-- ---------------------------------------------------------------------------
-- 8. Supporting indexes for the new join/filter paths
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS projects_state_fips ON projects (state_fips);
CREATE INDEX IF NOT EXISTS projects_status_code ON projects (status_code);
CREATE INDEX IF NOT EXISTS projects_csi_division_codes ON projects USING GIN (csi_division_codes);
CREATE INDEX IF NOT EXISTS projects_external_ids ON projects USING GIN (external_ids);

COMMIT;

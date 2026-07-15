-- Supreme Parts — additive schema tweaks for the RockAuto scraper.
-- Import AFTER schema.sql + staging.sql:
--   "C:/xampp/mysql/bin/mysql.exe" -u root -P 3307 supreme_parts < database/scrape_schema.sql
-- Purely ADDITIVE: new tables + nullable columns only. Breaks no existing storefront query.
-- (Council DATA-MODEL verdict: ~90% of RockAuto fields already fit; only these 3 concepts
--  had no home — interchange numbers, info/PDF docs, and warranty text.)

USE supreme_parts;

-- 1. Interchange / alternate (cross-reference) part numbers -----------------------
CREATE TABLE IF NOT EXISTS part_interchange (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  part_id     INT UNSIGNED NOT NULL,
  brand_name  VARCHAR(120) NULL,                       -- competitor / OE brand if given
  part_number VARCHAR(100) NOT NULL,                   -- alternate number (display form)
  number_norm VARCHAR(100) NOT NULL,                   -- normalized, for matching
  `type`      VARCHAR(20)  NOT NULL DEFAULT 'interchange',  -- interchange/oem/supersede
  UNIQUE KEY uq_pxref (part_id, number_norm),
  KEY idx_pxref_norm (number_norm),
  CONSTRAINT fk_pxref_part FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 2. Info links / PDFs / datasheets / install instructions -----------------------
CREATE TABLE IF NOT EXISTS part_documents (
  id       INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  part_id  INT UNSIGNED NOT NULL,
  `type`   VARCHAR(30)  NOT NULL DEFAULT 'info',       -- info/pdf/datasheet/install/warranty
  label    VARCHAR(160) NULL,
  url      VARCHAR(500) NOT NULL,
  position INT NOT NULL DEFAULT 0,
  KEY idx_pdoc_part (part_id),
  CONSTRAINT fk_pdoc_part FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 3. Warranty + provenance on parts (nullable -> storefront-safe) -----------------
-- Guarded so re-running is safe on MariaDB 10.4 (no IF NOT EXISTS on ADD COLUMN there).
SET @c := (SELECT COUNT(*) FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA='supreme_parts' AND TABLE_NAME='parts' AND COLUMN_NAME='warranty');
SET @s := IF(@c=0, 'ALTER TABLE parts ADD COLUMN warranty VARCHAR(160) NULL AFTER weight',
             'DO 0');
PREPARE st FROM @s; EXECUTE st; DEALLOCATE PREPARE st;

SET @c := (SELECT COUNT(*) FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA='supreme_parts' AND TABLE_NAME='parts' AND COLUMN_NAME='source_url');
SET @s := IF(@c=0, 'ALTER TABLE parts ADD COLUMN source_url VARCHAR(500) NULL AFTER primary_image_path',
             'DO 0');
PREPARE st FROM @s; EXECUTE st; DEALLOCATE PREPARE st;

-- 4. Staging carriers for the three new concepts + frontier payload ---------------
SET @c := (SELECT COUNT(*) FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA='supreme_parts' AND TABLE_NAME='stg_listings' AND COLUMN_NAME='warranty');
SET @s := IF(@c=0, 'ALTER TABLE stg_listings
                      ADD COLUMN warranty    VARCHAR(160) NULL,
                      ADD COLUMN interchange JSON NULL,
                      ADD COLUMN doc_urls    JSON NULL', 'DO 0');
PREPARE st FROM @s; EXECUTE st; DEALLOCATE PREPARE st;

-- stg_listings.variants: per-part "Choose Type" dropdown options as JSON
-- [{type,price_each,pack_total,raw}]; separate guard because the block above is
-- keyed on `warranty` which already exists on previously-migrated DBs.
SET @c := (SELECT COUNT(*) FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA='supreme_parts' AND TABLE_NAME='stg_listings' AND COLUMN_NAME='variants');
SET @s := IF(@c=0, 'ALTER TABLE stg_listings ADD COLUMN variants JSON NULL', 'DO 0');
PREPARE st FROM @s; EXECUTE st; DEALLOCATE PREPARE st;

-- 5. moreinfo detail enrichment (description/specs/features live only on
-- moreinfo.php). parts.moreinfo_key {pk,cc,pt} lets a pass fetch ONE detail page
-- per part; moreinfo_done gates resumability; stg_listings.moreinfo carries the
-- key from crawl through staging into the loader.
SET @c := (SELECT COUNT(*) FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA='supreme_parts' AND TABLE_NAME='parts' AND COLUMN_NAME='moreinfo_key');
SET @s := IF(@c=0, 'ALTER TABLE parts ADD COLUMN moreinfo_key VARCHAR(48) NULL AFTER source_url,
                      ADD COLUMN moreinfo_done TINYINT NOT NULL DEFAULT 0', 'DO 0');
PREPARE st FROM @s; EXECUTE st; DEALLOCATE PREPARE st;

SET @c := (SELECT COUNT(*) FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA='supreme_parts' AND TABLE_NAME='stg_listings' AND COLUMN_NAME='moreinfo');
SET @s := IF(@c=0, 'ALTER TABLE stg_listings ADD COLUMN moreinfo TEXT NULL', 'DO 0');
PREPARE st FROM @s; EXECUTE st; DEALLOCATE PREPARE st;

-- crawl_frontier.payload: carries the node jsn + accumulated fitment context so the
-- crawl is fully resumable across restarts without re-deriving state.
SET @c := (SELECT COUNT(*) FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA='supreme_parts' AND TABLE_NAME='crawl_frontier' AND COLUMN_NAME='payload');
SET @s := IF(@c=0, 'ALTER TABLE crawl_frontier ADD COLUMN payload JSON NULL', 'DO 0');
PREPARE st FROM @s; EXECUTE st; DEALLOCATE PREPARE st;

-- optional hardening the loader can exploit (safe, additive)
SET @c := (SELECT COUNT(*) FROM information_schema.STATISTICS
           WHERE TABLE_SCHEMA='supreme_parts' AND TABLE_NAME='engines' AND INDEX_NAME='uq_engines_name');
SET @s := IF(@c=0, 'ALTER TABLE engines ADD UNIQUE KEY uq_engines_name (name)', 'DO 0');
PREPARE st FROM @s; EXECUTE st; DEALLOCATE PREPARE st;

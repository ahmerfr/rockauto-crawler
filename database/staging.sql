-- Supreme Parts — additive staging tables for the ingest pipeline.
-- Import AFTER schema.sql:  mysql -u root supreme_parts < database/staging.sql
-- Purely additive: does NOT alter or drop any existing table.
-- Landing zone for the Reader (feed parser OR polite scraper); drained by the Loader.

USE supreme_parts;

DROP TABLE IF EXISTS stg_listings;
CREATE TABLE stg_listings (
  raw_id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  source         VARCHAR(20) NOT NULL,             -- 'aces_pies' | 'rockauto'
  source_url     VARCHAR(500) NULL,
  make_name      VARCHAR(120) NULL,
  model_name     VARCHAR(120) NULL,
  `year`         SMALLINT UNSIGNED NULL,
  engine_name    VARCHAR(120) NULL,
  liters         DECIMAL(3,1) NULL,
  cylinders      TINYINT UNSIGNED NULL,
  fuel_type      VARCHAR(30) NULL,
  aspiration     VARCHAR(30) NULL,
  trim           VARCHAR(80) NULL,
  category_path  VARCHAR(400) NULL,                -- 'Brake & Wheel Hub>Brake Pad'
  brand_name     VARCHAR(120) NULL,
  part_number    VARCHAR(100) NULL,
  name           VARCHAR(255) NULL,
  description    TEXT NULL,
  price          DECIMAL(10,2) NULL,
  core_charge    DECIMAL(10,2) NULL,
  weight         DECIMAL(8,2) NULL,
  image_urls     JSON NULL,
  attributes     JSON NULL,                        -- [{"name":..,"value":..}, ...]
  warehouse_code VARCHAR(30) NULL,
  quantity       INT NULL,
  fitment_note   VARCHAR(255) NULL,                -- per-vehicle note (ACES Position/Note)
  batch_id       VARCHAR(40) NOT NULL,
  processed      TINYINT(1) NOT NULL DEFAULT 0,
  scraped_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_stg_proc (processed, batch_id)
) ENGINE=InnoDB;

DROP TABLE IF EXISTS stg_fitment;
CREATE TABLE stg_fitment (
  raw_id       BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  sku          VARCHAR(120) NOT NULL,              -- deterministic, matches parts.sku
  make_name    VARCHAR(120) NOT NULL,
  model_name   VARCHAR(120) NOT NULL,
  `year`       SMALLINT UNSIGNED NOT NULL,
  engine_name  VARCHAR(120) NULL,
  trim         VARCHAR(80) NULL,
  note         VARCHAR(255) NULL,
  batch_id     VARCHAR(40) NOT NULL,
  processed    TINYINT(1) NOT NULL DEFAULT 0,
  KEY idx_stgfit_proc (processed, batch_id),
  KEY idx_stgfit_sku (sku)
) ENGINE=InnoDB;

-- Crawl frontier for the polite scraper (resumable node state).
DROP TABLE IF EXISTS crawl_frontier;
CREATE TABLE crawl_frontier (
  id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  node_type  VARCHAR(20) NOT NULL,                 -- make/year/model/engine/category/group/listing
  node_key   VARCHAR(255) NOT NULL,                -- stable identifier (href/carcode/etc.)
  href       VARCHAR(500) NULL,
  `status`   ENUM('pending','in_flight','done','failed') NOT NULL DEFAULT 'pending',
  attempts   TINYINT UNSIGNED NOT NULL DEFAULT 0,
  batch_id   VARCHAR(40) NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_frontier_node (node_type, node_key),
  KEY idx_frontier_status (`status`)
) ENGINE=InnoDB;

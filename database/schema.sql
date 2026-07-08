-- Supreme Parts — MySQL/MariaDB schema (XAMPP)
-- Import:  mysql -u root < database/schema.sql
--    or:   phpMyAdmin → Import → this file
-- Engine: InnoDB, utf8mb4. Safe to re-run (drops + recreates).

DROP DATABASE IF EXISTS supreme_parts;
CREATE DATABASE supreme_parts CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE supreme_parts;

-- ---------- VEHICLE TREE (Year / Make / Model / Engine) ----------

CREATE TABLE makes (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name       VARCHAR(80)  NOT NULL,
  slug       VARCHAR(100) NOT NULL,
  logo_path  VARCHAR(255) NULL,
  is_active  TINYINT(1)   NOT NULL DEFAULT 1,
  created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_makes_slug (slug)
) ENGINE=InnoDB;

CREATE TABLE engines (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name       VARCHAR(80) NOT NULL,          -- e.g. "1.8L L4"
  liters     DECIMAL(3,1) NULL,
  cylinders  TINYINT UNSIGNED NULL,
  fuel_type  VARCHAR(30) NULL,              -- Gas / Diesel / Hybrid / EV
  aspiration VARCHAR(30) NULL,              -- NA / Turbo / Supercharged
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE models (
  id        INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  make_id   INT UNSIGNED NOT NULL,
  name      VARCHAR(100) NOT NULL,
  slug      VARCHAR(120) NOT NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  UNIQUE KEY uq_models (make_id, slug),
  KEY idx_models_make (make_id),
  CONSTRAINT fk_models_make FOREIGN KEY (make_id) REFERENCES makes(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- A concrete, selectable vehicle node (what fitment points at).
CREATE TABLE vehicles (
  id        INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  make_id   INT UNSIGNED NOT NULL,
  model_id  INT UNSIGNED NOT NULL,
  `year`    SMALLINT UNSIGNED NOT NULL,
  engine_id INT UNSIGNED NULL,
  trim      VARCHAR(80) NULL,
  slug      VARCHAR(180) NOT NULL,
  UNIQUE KEY uq_vehicle (make_id, model_id, `year`, engine_id, trim),
  -- Deterministic slug is the ingest idempotency anchor. It is never NULL, so it
  -- dedups vehicles even when trim/engine_id are NULL (NULLs are distinct in the
  -- composite unique above, which would otherwise re-insert trim-less vehicles).
  UNIQUE KEY uq_vehicles_slug (slug),
  KEY idx_vehicles_year (`year`),
  KEY idx_vehicles_model (model_id),
  KEY idx_vehicles_engine (engine_id),
  CONSTRAINT fk_veh_make   FOREIGN KEY (make_id)   REFERENCES makes(id)   ON DELETE CASCADE,
  CONSTRAINT fk_veh_model  FOREIGN KEY (model_id)  REFERENCES models(id)  ON DELETE CASCADE,
  CONSTRAINT fk_veh_engine FOREIGN KEY (engine_id) REFERENCES engines(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------- CATALOG ----------

-- Self-referencing category tree (e.g. "Brake & Wheel Hub" > "Brake Pad").
-- NOTE: slug is globally unique for now to keep the CSV importer simple.
--       Phase 1 can relax this to UNIQUE(parent_id, slug) for true trees.
CREATE TABLE categories (
  id        INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  parent_id INT UNSIGNED NULL,
  name      VARCHAR(120) NOT NULL,
  slug      VARCHAR(140) NOT NULL,
  position  INT NOT NULL DEFAULT 0,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  UNIQUE KEY uq_categories_slug (slug),
  KEY idx_categories_parent (parent_id),
  CONSTRAINT fk_cat_parent FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE brands (
  id        INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name      VARCHAR(120) NOT NULL,
  slug      VARCHAR(140) NOT NULL,
  logo_path VARCHAR(255) NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_brands_slug (slug)
) ENGINE=InnoDB;

CREATE TABLE parts (
  id                INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  brand_id          INT UNSIGNED NULL,
  category_id       INT UNSIGNED NULL,
  part_number       VARCHAR(100) NOT NULL,
  sku               VARCHAR(120) NOT NULL,
  name              VARCHAR(255) NOT NULL,
  slug              VARCHAR(255) NOT NULL,
  description       TEXT NULL,
  price             DECIMAL(10,2) NOT NULL DEFAULT 0,
  core_charge       DECIMAL(10,2) NOT NULL DEFAULT 0,
  weight            DECIMAL(8,2) NULL,
  `status`          ENUM('active','inactive','discontinued') NOT NULL DEFAULT 'active',
  primary_image_path VARCHAR(255) NULL,
  created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_parts_sku (sku),
  KEY idx_parts_category (category_id),
  KEY idx_parts_brand (brand_id),
  KEY idx_parts_number (part_number),
  CONSTRAINT fk_parts_brand    FOREIGN KEY (brand_id)    REFERENCES brands(id)     ON DELETE SET NULL,
  CONSTRAINT fk_parts_category FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE part_images (
  id       INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  part_id  INT UNSIGNED NOT NULL,
  path     VARCHAR(255) NOT NULL,
  position INT NOT NULL DEFAULT 0,
  alt      VARCHAR(255) NULL,
  KEY idx_part_images_part (part_id),
  CONSTRAINT fk_pimg_part FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- The heart: which part fits which vehicle (many-to-many).
CREATE TABLE part_fitment (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  part_id    INT UNSIGNED NOT NULL,
  vehicle_id INT UNSIGNED NOT NULL,
  note       VARCHAR(255) NULL,           -- e.g. "Front", "w/o sport pkg"
  UNIQUE KEY uq_fitment (part_id, vehicle_id),
  KEY idx_fitment_vehicle (vehicle_id),
  CONSTRAINT fk_fit_part    FOREIGN KEY (part_id)    REFERENCES parts(id)    ON DELETE CASCADE,
  CONSTRAINT fk_fit_vehicle FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- PIES-style attributes (key/value specs per part).
CREATE TABLE part_attributes (
  id      INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  part_id INT UNSIGNED NOT NULL,
  name    VARCHAR(120) NOT NULL,
  `value` VARCHAR(255) NOT NULL,
  KEY idx_pattr_part (part_id),
  CONSTRAINT fk_pattr_part FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE inventory (
  id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  part_id        INT UNSIGNED NOT NULL,
  warehouse_code VARCHAR(30) NOT NULL DEFAULT 'MAIN',
  quantity       INT NOT NULL DEFAULT 0,
  restock_at     DATE NULL,
  UNIQUE KEY uq_inventory (part_id, warehouse_code),
  CONSTRAINT fk_inv_part FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------- CUSTOMERS / COMMERCE ----------

CREATE TABLE customers (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  email         VARCHAR(190) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  first_name    VARCHAR(80) NULL,
  last_name     VARCHAR(80) NULL,
  phone         VARCHAR(40) NULL,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_customers_email (email)
) ENGINE=InnoDB;

CREATE TABLE customer_vehicles (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  customer_id INT UNSIGNED NOT NULL,
  vehicle_id  INT UNSIGNED NOT NULL,
  UNIQUE KEY uq_cust_vehicle (customer_id, vehicle_id),
  CONSTRAINT fk_cv_customer FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
  CONSTRAINT fk_cv_vehicle  FOREIGN KEY (vehicle_id)  REFERENCES vehicles(id)  ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE addresses (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  customer_id INT UNSIGNED NOT NULL,
  `type`      ENUM('billing','shipping') NOT NULL DEFAULT 'shipping',
  line1       VARCHAR(190) NOT NULL,
  line2       VARCHAR(190) NULL,
  city        VARCHAR(120) NOT NULL,
  state       VARCHAR(80)  NOT NULL,
  postal_code VARCHAR(20)  NOT NULL,
  country     CHAR(2) NOT NULL DEFAULT 'US',
  is_default  TINYINT(1) NOT NULL DEFAULT 0,
  KEY idx_addr_customer (customer_id),
  CONSTRAINT fk_addr_customer FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE carts (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  customer_id   INT UNSIGNED NULL,
  session_token VARCHAR(64) NOT NULL,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_carts_token (session_token),
  KEY idx_carts_customer (customer_id),
  CONSTRAINT fk_carts_customer FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE cart_items (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  cart_id    INT UNSIGNED NOT NULL,
  part_id    INT UNSIGNED NOT NULL,
  quantity   INT NOT NULL DEFAULT 1,
  unit_price DECIMAL(10,2) NOT NULL,
  UNIQUE KEY uq_cart_item (cart_id, part_id),
  CONSTRAINT fk_ci_cart FOREIGN KEY (cart_id) REFERENCES carts(id) ON DELETE CASCADE,
  CONSTRAINT fk_ci_part FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE orders (
  id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  order_number   VARCHAR(30) NOT NULL,
  customer_id    INT UNSIGNED NULL,
  email          VARCHAR(190) NOT NULL,
  `status`       ENUM('pending','paid','processing','shipped','completed','cancelled','refunded')
                 NOT NULL DEFAULT 'pending',
  subtotal       DECIMAL(10,2) NOT NULL DEFAULT 0,
  shipping_total DECIMAL(10,2) NOT NULL DEFAULT 0,
  tax_total      DECIMAL(10,2) NOT NULL DEFAULT 0,
  grand_total    DECIMAL(10,2) NOT NULL DEFAULT 0,
  currency       CHAR(3) NOT NULL DEFAULT 'USD',
  placed_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_orders_number (order_number),
  KEY idx_orders_customer (customer_id),
  CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE order_items (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  order_id    INT UNSIGNED NOT NULL,
  part_id     INT UNSIGNED NULL,
  part_number VARCHAR(100) NOT NULL,
  name        VARCHAR(255) NOT NULL,
  quantity    INT NOT NULL,
  unit_price  DECIMAL(10,2) NOT NULL,
  line_total  DECIMAL(10,2) NOT NULL,
  KEY idx_oi_order (order_id),
  CONSTRAINT fk_oi_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  CONSTRAINT fk_oi_part  FOREIGN KEY (part_id)  REFERENCES parts(id)  ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE order_addresses (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  order_id    INT UNSIGNED NOT NULL,
  `type`      ENUM('billing','shipping') NOT NULL,
  name        VARCHAR(160) NULL,
  line1       VARCHAR(190) NOT NULL,
  line2       VARCHAR(190) NULL,
  city        VARCHAR(120) NOT NULL,
  state       VARCHAR(80)  NOT NULL,
  postal_code VARCHAR(20)  NOT NULL,
  country     CHAR(2) NOT NULL DEFAULT 'US',
  KEY idx_oa_order (order_id),
  CONSTRAINT fk_oa_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE payments (
  id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  order_id       INT UNSIGNED NOT NULL,
  gateway        VARCHAR(40) NOT NULL,        -- stripe / paypal
  gateway_txn_id VARCHAR(120) NULL,
  amount         DECIMAL(10,2) NOT NULL,
  `status`       VARCHAR(40) NOT NULL,        -- authorized / captured / failed / refunded
  created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_pay_order (order_id),
  CONSTRAINT fk_pay_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------- ADMIN / OPS ----------

CREATE TABLE roles (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(60) NOT NULL,
  permissions JSON NULL,
  UNIQUE KEY uq_roles_name (name)
) ENGINE=InnoDB;

CREATE TABLE admins (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  email         VARCHAR(190) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  name          VARCHAR(120) NOT NULL,
  role_id       INT UNSIGNED NULL,
  is_active     TINYINT(1) NOT NULL DEFAULT 1,
  last_login_at TIMESTAMP NULL,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_admins_email (email),
  KEY idx_admins_role (role_id),
  CONSTRAINT fk_admins_role FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE import_logs (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  admin_id    INT UNSIGNED NULL,
  `type`      VARCHAR(40) NOT NULL,           -- parts_csv / fitment_csv / vpic / aces_pies
  filename    VARCHAR(255) NULL,
  rows_total  INT NOT NULL DEFAULT 0,
  rows_ok     INT NOT NULL DEFAULT 0,
  rows_failed INT NOT NULL DEFAULT 0,
  `status`    VARCHAR(30) NOT NULL DEFAULT 'completed',
  message     TEXT NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_implog_admin (admin_id),
  CONSTRAINT fk_implog_admin FOREIGN KEY (admin_id) REFERENCES admins(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE settings (
  id      INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `key`   VARCHAR(80) NOT NULL,
  `value` TEXT NULL,
  UNIQUE KEY uq_settings_key (`key`)
) ENGINE=InnoDB;

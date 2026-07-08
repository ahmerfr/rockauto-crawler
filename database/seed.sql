-- Supreme Parts — demo seed data (dev only)
-- Import AFTER schema.sql:  mysql -u root supreme_parts < database/seed.sql
-- Gives the storefront a few real-looking rows so it isn't empty during dev.
-- Replace with your licensed catalog via the CSV importer (see docs/supreme-parts/ROADMAP.md).

USE supreme_parts;

INSERT INTO makes (id, name, slug) VALUES
 (1,'Honda','honda'), (2,'Toyota','toyota'), (3,'Ford','ford');

INSERT INTO models (id, make_id, name, slug) VALUES
 (1,1,'Civic','civic'), (2,1,'Accord','accord'),
 (3,2,'Camry','camry'), (4,3,'F-150','f-150');

INSERT INTO engines (id, name, liters, cylinders, fuel_type) VALUES
 (1,'1.8L L4',1.8,4,'Gas'),
 (2,'2.4L L4',2.4,4,'Gas'),
 (3,'5.0L V8',5.0,8,'Gas');

INSERT INTO vehicles (id, make_id, model_id, `year`, engine_id, trim, slug) VALUES
 (1,1,1,2015,1,'LX','2015-honda-civic-1-8l'),
 (2,1,2,2016,2,'Sport','2016-honda-accord-2-4l'),
 (3,2,3,2015,2,'LE','2015-toyota-camry-2-4l'),
 (4,3,4,2017,3,'XLT','2017-ford-f-150-5-0l');

INSERT INTO categories (id, parent_id, name, slug, position) VALUES
 (1,NULL,'Brake & Wheel Hub','brake-wheel-hub',1),
 (2,1,'Brake Pad','brake-pad',1),
 (3,NULL,'Engine','engine',2),
 (4,3,'Oil Filter','oil-filter',1);

INSERT INTO brands (id, name, slug) VALUES
 (1,'Bosch','bosch'), (2,'ACDelco','acdelco'), (3,'Wagner','wagner');

INSERT INTO parts (id, brand_id, category_id, part_number, sku, name, slug, description, price, core_charge) VALUES
 (1,1,2,'BP1234','BOSCH-BP1234','Bosch QuietCast Front Brake Pad Set','bosch-quietcast-brake-pad-bp1234','Ceramic front brake pad set with hardware.',42.99,0),
 (2,3,2,'ZD923','WAGNER-ZD923','Wagner ThermoQuiet Front Brake Pad Set','wagner-thermoquiet-zd923','Ceramic front brake pads, low dust.',38.50,0),
 (3,2,4,'PF2257','ACDELCO-PF2257','ACDelco Engine Oil Filter','acdelco-oil-filter-pf2257','Spin-on engine oil filter.',9.75,0);

INSERT INTO inventory (part_id, warehouse_code, quantity) VALUES
 (1,'MAIN',120), (2,'MAIN',80), (3,'MAIN',300);

INSERT INTO part_fitment (part_id, vehicle_id) VALUES
 (1,1),(1,2),(2,1),(3,1),(3,2),(3,3);

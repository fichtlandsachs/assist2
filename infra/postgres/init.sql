-- Erstellt separate Datenbanken für Backend und n8n
CREATE DATABASE n8n_db;
GRANT ALL PRIVILEGES ON DATABASE n8n_db TO platform;

\c platform_db
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

\c n8n_db
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

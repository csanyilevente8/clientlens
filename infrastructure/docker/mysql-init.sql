-- Runs automatically on first MySQL container init (mounted into /docker-entrypoint-initdb.d).
-- Creates the test database and grants the app user access, so integration tests can
-- create/drop tables in an isolated DB without needing root.
CREATE DATABASE IF NOT EXISTS clientlens_test;
GRANT ALL PRIVILEGES ON clientlens_test.* TO 'clientlens'@'%';
FLUSH PRIVILEGES;

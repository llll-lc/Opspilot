CREATE DATABASE op001_target;

\connect op001_target

CREATE TABLE service_probe (
    id integer PRIMARY KEY,
    service_name text NOT NULL,
    status text NOT NULL
);

INSERT INTO service_probe (id, service_name, status)
VALUES (1, 'superset', 'seeded');

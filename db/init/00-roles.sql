-- Runs once when the local Postgres volume is first created.
-- Remote has an `admin` runtime role that migrations V2 and V3 grant SELECT to.
CREATE ROLE admin NOLOGIN;

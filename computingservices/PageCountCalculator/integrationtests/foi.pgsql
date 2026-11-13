-- DAL projection of request-management-api/request_api/models/FOIMinistryRequests.py
-- and migrations/versions/67e0b98b63ea_rename_add_recordspagecount.py.
-- Preserve varchar counts: psycopg2 returns text, affecting shortcut selection.
CREATE TABLE "FOIMinistryRequests" (
 foiministryrequestid integer, version integer NOT NULL, isactive boolean NOT NULL,
 recordspagecount varchar(20), updated_at timestamp, updatedby varchar(120),
 PRIMARY KEY(foiministryrequestid, version));

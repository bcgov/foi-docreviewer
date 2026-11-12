-- Disposable DAL projection of api/reviewer_api/models/{DocumentMaster,
-- DocumentAttributes,Documents,DocumentHashCodes,DocumentDeleted,
-- DeduplicationJob,PageCalculatorJob}.py. Only queried columns are included.
-- This is test infrastructure, not an application migration.
CREATE TABLE "DocumentMaster" (
 documentmasterid integer, filepath varchar(500), ministryrequestid integer NOT NULL,
 recordid integer, processingparentid integer, parentid integer,
 created_at timestamp DEFAULT now(), createdby varchar(120),
 PRIMARY KEY(documentmasterid, filepath));
CREATE TABLE "DocumentAttributes" (
 attributeid serial PRIMARY KEY, documentmasterid integer,
 attributes json NOT NULL, isactive boolean NOT NULL);
CREATE TABLE "Documents" (
 documentid integer, version integer, documentmasterid integer,
 foiministryrequestid integer, filename varchar(500), pagecount integer,
 PRIMARY KEY(documentid, version));
CREATE TABLE "DocumentHashCodes" (documentid integer PRIMARY KEY, rank1hash varchar NOT NULL);
CREATE TABLE "DocumentDeleted" (filepath varchar(500) NOT NULL, ministryrequestid integer);
CREATE TABLE "DeduplicationJob" (
 deduplicationjobid integer, version integer, ministryrequestid integer,
 documentmasterid varchar(240), filename varchar(500),
 PRIMARY KEY(deduplicationjobid, version));
CREATE TABLE "PageCalculatorJob" (
 pagecalculatorjobid integer, version integer NOT NULL, ministryrequestid integer NOT NULL,
 inputmessage json NOT NULL, pagecount json, status varchar(120) NOT NULL,
 message text, createdat timestamp NOT NULL DEFAULT now(), createdby varchar(120) NOT NULL,
 PRIMARY KEY(pagecalculatorjobid, version));

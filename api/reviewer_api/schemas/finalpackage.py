from marshmallow import Schema, fields


class FileSchema(Schema):
    s3uripath = fields.Str(data_key="s3uripath", allow_none=False)
    filename = fields.Str(data_key="filename", allow_none=False)
    recordname = fields.Str(data_key="recordname", allow_none=False)
    documentid = fields.Int(data_key="documentid", allow_none=True)

class AttributeSchema(Schema):
    files = fields.Nested(FileSchema, many=True, required=True, allow_none=False)


class SummaryPkgSchema(Schema):
    divisionid = fields.Int(data_key="divisionid", allow_none=True)
    recordname = fields.Str(data_key="recordname", allow_none=True)
    documentids = fields.List(fields.Int(), allow_none=True)

class SummarySchema(Schema):
    pkgdocuments = fields.List(fields.Nested(SummaryPkgSchema, allow_none=True))
    sorteddocuments = fields.List(fields.Int())

class FinalPackageSchema(Schema):
    ministryrequestid = fields.Str(data_key="ministryrequestid", allow_none=False)
    category = fields.Str(data_key="category", allow_none=False)
    requestnumber = fields.Str(data_key="requestnumber", allow_none=False)
    bcgovcode = fields.Str(data_key="bcgovcode", allow_none=False)
    attributes = fields.Nested(
        AttributeSchema, many=True, required=True, allow_none=False
    )
    summarydocuments = fields.Nested(SummarySchema, allow_none=True)
    redactionlayerid = fields.Int(data_key="redactionlayerid", allow_none=False)
    requesttype = fields.Str(data_key="requesttype", allow_none=False)

class SummaryRecordSchema(Schema):
    recordname = fields.Str(data_key="recordname", allow_none=True)
    documentids = fields.List(fields.Int(), allow_none=True)

class MCFSummaryPkgSchema(Schema):
    divisionid = fields.Int(data_key="divisionid", allow_none=True)
    documentids = fields.List(fields.Int(), allow_none=True)
    records = fields.List(fields.Nested(SummaryRecordSchema), allow_none=True)

class MCFSummarySchema(Schema):
    pkgdocuments = fields.List(fields.Nested(MCFSummaryPkgSchema, allow_none=True))
    sorteddocuments = fields.List(fields.Int())

class MCFFinalPackageSchema(Schema):
    ministryrequestid = fields.Str(data_key="ministryrequestid", allow_none=False)
    category = fields.Str(data_key="category", allow_none=False)
    requestnumber = fields.Str(data_key="requestnumber", allow_none=False)
    bcgovcode = fields.Str(data_key="bcgovcode", allow_none=False)
    attributes = fields.Nested(
        AttributeSchema, many=True, required=True, allow_none=False
    )
    summarydocuments = fields.Nested(MCFSummarySchema, allow_none=True)
    redactionlayerid = fields.Int(data_key="redactionlayerid", allow_none=False)
    requesttype = fields.Str(data_key="requesttype", allow_none=False)
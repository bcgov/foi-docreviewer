from marshmallow import Schema, fields


class FileSchema(Schema):
    s3uripath = fields.Str(data_key="s3uripath", allow_none=False)
    filename = fields.Str(data_key="filename", allow_none=False)

class AttributeSchema(Schema):
    files = fields.Nested(FileSchema, many=True, required=True, allow_none=False)
    divisionname = fields.Str(data_key="divisionname", allow_none=True)
    divisionid = fields.Int(data_key="divisionid", allow_none=True)
    includeduplicatepages = fields.Boolean(data_key="includeduplicatepages", allow_none=True)
    includenrpages = fields.Boolean(data_key="includenrpages", allow_none=True)
    phase = fields.Int(data_key="phase", allow_none=True)
    includecomments = fields.Boolean(data_key="includecomments", allow_none=True)

class SummaryPkgSchema(Schema):
    divisionid = fields.Int(data_key="divisionid", allow_none=True)
    documentids = fields.List(fields.Int())

class SummarySchema(Schema):
    pkgdocuments = fields.List(fields.Nested(SummaryPkgSchema, allow_none=True))
    sorteddocuments = fields.List(fields.Int())

class RedlineSchema(Schema):
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
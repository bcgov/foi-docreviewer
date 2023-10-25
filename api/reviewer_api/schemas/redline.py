from marshmallow import Schema, fields


class FileSchema(Schema):
    s3uripath = fields.Str(data_key="s3uripath", allow_none=False)
    filename = fields.Str(data_key="filename", allow_none=False)


class AttributeSchema(Schema):
    files = fields.Nested(FileSchema, many=True, required=True, allow_none=False)
    divisionname = fields.Str(data_key="divisionname", allow_none=True)
    divisionid = fields.Int(data_key="divisionid", allow_none=True)


class RedlineSchema(Schema):
    ministryrequestid = fields.Str(data_key="ministryrequestid", allow_none=False)
    category = fields.Str(data_key="category", allow_none=False)
    requestnumber = fields.Str(data_key="requestnumber", allow_none=False)
    bcgovcode = fields.Str(data_key="bcgovcode", allow_none=False)
    attributes = fields.Nested(
        AttributeSchema, many=True, required=True, allow_none=False
    )
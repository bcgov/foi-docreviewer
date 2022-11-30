from marshmallow import EXCLUDE, Schema, fields


class AnnotationRequest(Schema):
    class Meta:
        unknown = EXCLUDE

    xml = fields.Str(data_key="xml",allow_none=False) 
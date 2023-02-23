from marshmallow import EXCLUDE, Schema, fields

class SectionSchema(Schema):
    class Meta:  # pylint: disable=too-few-public-methods
        """Exclude unknown fields in the deserialized output."""
        unknown = EXCLUDE
    id = fields.Int(data_key="id",allow_none=False) 
    section = fields.Str(data_key="section",allow_none=False) 

class SectionAnnotationSchema(Schema):
    class Meta:  # pylint: disable=too-few-public-methods
        """Exclude unknown fields in the deserialized output."""
        unknown = EXCLUDE
    annotation = fields.Str(data_key="annotation",allow_none=False) 


class SectionRequestSchema(Schema):       
    foiministryrequestid = fields.Int(data_key="foiministryrequestid",allow_none=False)
    ids = fields.List(fields.Nested(SectionSchema))
    parts = fields.List(fields.Nested(SectionAnnotationSchema),allow_none=False)
    
class AnnotationRequest(Schema):
    xml = fields.Str(data_key="xml",allow_none=False)      
    sections = fields.Nested(SectionRequestSchema, allow_none=True)


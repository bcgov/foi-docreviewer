from marshmallow import EXCLUDE, Schema, fields, pre_load
from reviewer_api.schemas.documentpageflag import BulkDocumentPageflagSchema
import json


class SectionSchema(Schema):
    class Meta:  # pylint: disable=too-few-public-methods
        """Exclude unknown fields in the deserialized output."""

        unknown = EXCLUDE

    id = fields.Int(data_key="id", allow_none=False)
    section = fields.Str(data_key="section", allow_none=False)


class SectionAnnotationSchema(Schema):
    @pre_load(pass_many=True)
    def decode_sections_json(self, data, many, **kwargs):
        data["sections"] = json.loads(data.get("sections", "[]"))
        return data

    class Meta:  # pylint: disable=too-few-public-methods
        unknown = EXCLUDE

    ids = fields.List(fields.Nested(SectionSchema), data_key="sections")
    redactannotation = fields.Str(data_key="parentRedaction", allow_none=False)


class SectionRequestSchema(Schema):
    foiministryrequestid = fields.Int(data_key="foiministryrequestid", allow_none=False)


class BulkPageFlagSchema(Schema):
    class Meta:  # pylint: disable=too-few-public-methods
        """Exclude unknown fields in the deserialized output."""

        unknown = EXCLUDE

    page = fields.Int(data_key="page", allow_none=True)
    flagid = fields.Int(data_key="flagid", allow_none=False)


class AnnotationRequest(Schema):
    xml = fields.Str(data_key="xml", allow_none=False)
    sections = fields.Nested(SectionRequestSchema, allow_none=True)
    pageflags = fields.Nested(BulkDocumentPageflagSchema, allow_none=True)
    foiministryrequestid = fields.Int(data_key="foiministryrequestid", allow_none=True)
    redactionlayerid = fields.Int(data_key="redactionlayerid", allow_none=True)


# new schemas added for bult delete annotations
class AnnotationRequestSchema(Schema):
    annotationname = fields.Str(data_key="name", allow_none=False)
    type = fields.Str(data_key="type", allow_none=False)
    page = fields.Int(data_key="page", allow_none=False)
    docid = fields.Int(data_key="docid", allow_none=False)
    docversion = fields.Int(data_key="docversion", allow_none=False)


# new schemas added for bult delete annotations
class BulkAnnotationRequest(Schema):
    annotations = fields.Nested(
        AnnotationRequestSchema, many=True, required=True, allow_none=False
    )



from marshmallow import EXCLUDE, Schema, fields, validate
from reviewer_api.utils.constants import MAX_EXCEPTION_MESSAGE

"""
This class  consolidates schemas of record operations.

__author__      = "sumathi.thirumani@aot-technologies.com"

"""

class PageflagSchema(Schema):
    class Meta:  # pylint: disable=too-few-public-methods
        """Exclude unknown fields in the deserialized output."""
        unknown = EXCLUDE
    page = fields.Int(data_key="page",allow_none=False) 
    flagid = fields.Int(data_key="flagid",allow_none=True) 
    deleted = fields.Boolean(data_key="deleted",allow_none=True) 
    programareaid =fields.List(fields.Int(allow_none=True), data_key="programareaid",allow_none=True)
    other = fields.List(fields.Str(allow_none=True), data_key="other",allow_none=True)
    publicbodyaction=fields.Str(data_key="publicbodyaction",allow_none=True)
    redactiontype=fields.Str(data_key="redactiontype",allow_none=True)
    phase =fields.List(fields.Int(allow_none=True), data_key="phase",allow_none=True)

class DocumentPageflagSchema(Schema):
    class Meta:  # pylint: disable=too-few-public-methods
        """Exclude unknown fields in the deserialized output."""

        unknown = EXCLUDE    
    documentid = fields.Int(data_key="documentid",allow_none=False) 
    version = fields.Int(data_key="version",allow_none=False) 
    pageflags = fields.Nested(PageflagSchema, many=True, validate=validate.Length(min=1), required=True,allow_none=False)
    redactionlayerid = fields.Int(data_key="redactionlayerid",allow_none=True)

class BulkDocumentPageflagSchema(Schema):
    class Meta:  # pylint: disable=too-few-public-methods
        """Exclude unknown fields in the deserialized output."""

        unknown = EXCLUDE    
    documentpageflags = fields.Nested(DocumentPageflagSchema, many=True, validate=validate.Length(min=1), required=True,allow_none=False)



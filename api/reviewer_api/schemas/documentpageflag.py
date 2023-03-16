

from marshmallow import EXCLUDE, Schema, fields, validate
from reviewer_api.utils.constants import MAX_EXCEPTION_MESSAGE

"""
This class  consolidates schemas of record operations.

__author__      = "sumathi.thirumani@aot-technologies.com"

"""

class DocumentPageflagSchema(Schema):
    class Meta:  # pylint: disable=too-few-public-methods
        """Exclude unknown fields in the deserialized output."""
        unknown = EXCLUDE
    page = fields.Int(data_key="page",allow_none=False) 
    flagid = fields.Int(data_key="flagid",allow_none=False) 
    programareaid = fields.Int(data_key="programareaid",allow_none=True)
    other = fields.Str(data_key="other",allow_none=True)
    publicbodyaction=fields.Str(data_key="publicbodyaction",allow_none=True)


class FOIRequestDocumentPageflagSchema(Schema):
    class Meta:  # pylint: disable=too-few-public-methods
        """Exclude unknown fields in the deserialized output."""

        unknown = EXCLUDE
    pageflag = fields.List(fields.Nested(DocumentPageflagSchema))
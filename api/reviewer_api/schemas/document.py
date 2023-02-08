

from marshmallow import EXCLUDE, Schema, fields, validate
from reviewer_api.utils.constants import MAX_EXCEPTION_MESSAGE

"""
This class  consolidates schemas of record operations.

__author__      = "sumathi.thirumani@aot-technologies.com"

"""
class FOIRequestDeleteRecordsSchema(Schema):
    class Meta:  # pylint: disable=too-few-public-methods
        """Exclude unknown fields in the deserialized output."""

        unknown = EXCLUDE
    filepaths = fields.List(fields.String(validate=[validate.Length(max=1000, error=MAX_EXCEPTION_MESSAGE)]), data_key="filepaths",allow_none=False)
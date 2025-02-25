

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
    ministryrequestid = fields.Int(data_key="ministryrequestid",allow_none=False)

class DivisionSchema(Schema):
    class Meta:  # pylint: disable=too-few-public-methods
        """Exclude unknown fields in the deserialized output."""

        unknown = EXCLUDE 
    divisionid = fields.Int(data_key="divisionid",allow_none=False)

class PersonalAttributesSchema(Schema):
    class Meta:  # pylint: disable=too-few-public-methods
        """Exclude unknown fields in the deserialized output."""

        unknown = EXCLUDE 
    person = fields.Str(data_key="person",allow_none=True)
    filetype = fields.Str(data_key="filetype",allow_none=True)
    volume = fields.Str(data_key="volume",allow_none=True)
    trackingid = fields.Str(data_key="trackingid",allow_none=True)
    personaltag = fields.Str(data_key="personaltag",allow_none=True)

class FOIRequestUpdateRecordsSchema(Schema):
    class Meta:  # pylint: disable=too-few-public-methods
        """Exclude unknown fields in the deserialized output."""

        unknown = EXCLUDE
    documentmasterids = fields.List(fields.Integer(),data_key="documentmasterids",allow_none=False)
    ministryrequestid = fields.Int(data_key="ministryrequestid",allow_none=False)
    divisions = fields.Nested(DivisionSchema,many=True,validate=validate.Length(min=1),allow_none=True,required=False)
    rotatedpages = fields.Dict(keys=fields.Str,values=fields.Int,allow_none=True,required=False) # {page: rotation in degrees}

class FOIRequestUpdateRecordPersonalAttributesSchema(Schema):
    class Meta:  # pylint: disable=too-few-public-methods
        """Exclude unknown fields in the deserialized output."""

        unknown = EXCLUDE
    documentmasterids = fields.List(fields.Integer(),data_key="documentmasterids",allow_none=False)
    ministryrequestid = fields.Int(data_key="ministryrequestid",allow_none=True)
    personalattributes = fields.Nested(PersonalAttributesSchema,required=False,allow_none=False)

class DocumentPage(Schema):
    class Meta:  # pylint: disable=too-few-public-methods
        """Exclude unknown fields in the deserialized output."""

        unknown = EXCLUDE 
    docid = fields.Int(data_key="docid",allow_none=False)
    pages = fields.List(fields.Integer(),data_key="pages",allow_none=False)

class DocumentDeletedPage(Schema):
    class Meta:  # pylint: disable=too-few-public-methods
        """Exclude unknown fields in the deserialized output."""

        unknown = EXCLUDE 
    redactionlayer = fields.String(data_key="redactionlayer",allow_none=False)
    documentpages = fields.Nested(DocumentPage,many=True,validate=validate.Length(min=1),allow_none=False)

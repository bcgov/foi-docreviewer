from .db import  db, ma
from .default_method_result import DefaultMethodResult
from sqlalchemy import and_
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime as datetime2
from sqlalchemy import text
import logging

class DocumentAttributes(db.Model):
    __tablename__ = 'DocumentAttributes' 
    # Defining the columns
    attributeid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    version = db.Column(db.Integer, primary_key=True, nullable=False)
    documentmasterid = db.Column(db.Integer, db.ForeignKey('DocumentMaster.documentmasterid'))
    attributes = db.Column(JSON, unique=False, nullable=False)
    createdby = db.Column(JSON, unique=False, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime2.now)
    updatedby = db.Column(JSON, unique=False, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True)
    isactive = db.Column(db.Boolean, unique=False, default=True, nullable=False)

    @classmethod
    def getdocumentattributes(cls, documentmasterid):
        attributes_schema = DocumentAttributeSchema(many=True)
        query = db.session.query(DocumentAttributes).filter(DocumentAttributes.documentmasterid == documentmasterid).first()
        return attributes_schema.dump(query)

    @classmethod
    def getdocumentattributesbyid(cls, documentmasterids):
        attributes = []
        try:
            sql =   """select attributeid, version, documentmasterid, attributes, createdby, created_at, updatedby, updated_at, isactive
                        from "DocumentAttributes"
                        where documentmasterid in ("""+ ','.join([str(id) for id in documentmasterids]) +""") and isactive = True
                        order by documentmasterid
                    """
            rs = db.session.execute(text(sql))

            for row in rs:
                attributes.append({
                    "attributeid": row["attributeid"],
                    "version": row["version"],
                    "documentmasterid": row["documentmasterid"],
                    "attributes": row["attributes"],
                    "createdby": row["createdby"],
                    "created_at": row["created_at"],
                    "updatedby": row["updatedby"],
                    "updated_at": row["updated_at"],
                    "isactive": row["isactive"]
                })
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()
        return attributes

    @classmethod
    def create(cls, rows, oldrows):
        # disable old rows
        db.session.bulk_update_mappings(DocumentAttributes, oldrows)

        db.session.add_all(rows)
        db.session.commit()
        return DefaultMethodResult(True,'Attributes added for document master ids', -1, [{"id": row.documentmasterid} for row in rows])


class DocumentAttributeSchema(ma.Schema):
    class Meta:
        fields = ('attributeid', 'version', 'documentmasterid', 'attributes', 'createdby', 'created_at', 'updatedby', 'updated_at')
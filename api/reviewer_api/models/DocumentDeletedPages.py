from .db import db, ma
from datetime import datetime as datetime2
from sqlalchemy.dialects.postgresql import JSON, insert
from sqlalchemy import or_, and_, text
from .default_method_result import DefaultMethodResult
import logging

class DocumentDeletedPage(db.Model):
    __tablename__ = 'DocumentDeletedPages'
    # Defining the columns
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    version = db.Column(db.Integer, primary_key=True, nullable=False)
    redactionlayerid = db.Column(db.Integer, primary_key=True, nullable=False)
    ministryrequestid = db.Column(db.Integer, nullable=False)    
    pagemetadata = db.Column(JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime2.now)
    createdby = db.Column(JSON, unique=False, nullable=False)

    
    @classmethod
    def create(cls, ministryrequestid, redactionlayerid, pageinfo, userinfo) -> DefaultMethodResult:
        try:
            deletepagekey = cls.__getkey(ministryrequestid, redactionlayerid)
            value = {
                    "redactionlayerid": redactionlayerid,
                    "ministryrequestid": ministryrequestid,                    
                    "pagemetadata": pageinfo,
                    "createdby": userinfo                    
                }
            if deletepagekey is not None:
                value["id"] = deletepagekey[0]
                value["version"] = deletepagekey[1]+1
            else:
                value["version"] = 1
            
            insertstmt = insert(DocumentDeletedPage).values([value])
            db.session.execute(insertstmt)
            db.session.commit()
            return DefaultMethodResult(True, "Deleted page details saved", ministryrequestid)
        except Exception as ex:
            logging.error(ex)
            return DefaultMethodResult(False, "Deleted page details persist operation failed", ministryrequestid)
        finally:
            db.session.close()

    @classmethod
    def getdeletedpages(cls, ministryrequestid, redactionlayerid):
        try:
            deletepage_schema = DocumentDeletedSchema(many=True)
            query = db.session.query(DocumentDeletedPage).filter(DocumentDeletedPage.ministryrequestid == ministryrequestid, DocumentDeletedPage.redactionlayerid ==  redactionlayerid).all()
            return deletepage_schema.dump(query)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def __getkey(cls, ministryrequestid, redactionlayerid):
        try:
            return (
                db.session.query(DocumentDeletedPage.id, DocumentDeletedPage.version)
                .filter(and_(DocumentDeletedPage.ministryrequestid == ministryrequestid, DocumentDeletedPage.redactionlayerid == redactionlayerid))
                .order_by(DocumentDeletedPage.version.desc())
                .first()
            )
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()
     
class DocumentDeletedSchema(ma.Schema):
    class Meta:
        fields = ('id', 'version', 'redactionlayerid', 'ministryrequestid', 'pagemetadata', 'created_at', 'createdby')
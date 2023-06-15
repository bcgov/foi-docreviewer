from .db import  db, ma
from .default_method_result import DefaultMethodResult
from sqlalchemy import or_, and_
from sqlalchemy.dialects.postgresql import JSON, insert
from datetime import datetime
from sqlalchemy.orm import relationship, backref, aliased
import logging

class Annotation(db.Model):
    __tablename__ = 'Annotations'
    # Defining the columns
    annotationid = db.Column(db.Integer, primary_key=True,autoincrement=True)
    annotationname = db.Column(db.String(120), unique=True, nullable=False)
    documentid = db.Column(db.Integer, db.ForeignKey('Documents.documentid'))
    documentversion = db.Column(db.Integer, db.ForeignKey('Documents.version'))
    annotation = db.Column(db.Text, unique=False, nullable=False)
    pagenumber = db.Column(db.Integer, nullable=False)
    isactive = db.Column(db.Boolean, unique=False, nullable=False)
    createdby = db.Column(JSON, unique=False, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updatedby = db.Column(JSON, unique=False, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True)
    
    sections = relationship('AnnotationSection', primaryjoin="and_(Annotation.annotationname==AnnotationSection.annotationname)") 
    

    @classmethod
    def getannotations(cls, _documentid, _documentversion):
        annotation_schema = AnnotationSchema(many=True)
        query = db.session.query(Annotation).filter(and_(Annotation.documentid == _documentid, Annotation.documentversion == _documentversion, Annotation.isactive==True)).order_by(Annotation.annotationid.asc()).all()
        return annotation_schema.dump(query)

    @classmethod
    def getredactionsbypage(cls, _documentid, _documentversion, _pagenum):
        annotation_schema = AnnotationSchema(many=True)
        query = db.session.query(Annotation).filter(
            and_(
                Annotation.documentid == _documentid,
                Annotation.documentversion == _documentversion,
                Annotation.isactive==True,
                Annotation.pagenumber == _pagenum-1,
                Annotation.annotation.ilike('%<redact %')
            )).order_by(Annotation.annotationid.asc()).all()
        return annotation_schema.dump(query)
    
    @classmethod
    def getannotationinfo(cls, _documentid, _documentversion):
        annotation_schema = AnnotationSchema(many=True)
        query = db.session.query(Annotation.annotationname).filter(and_(Annotation.documentid == _documentid, Annotation.documentversion == _documentversion, Annotation.isactive==True)).order_by(Annotation.annotationid.asc()).all()
        return annotation_schema.dump(query)

    @classmethod
    def getannotationid(cls, _annotationname):
        return db.session.query(Annotation.annotationid).filter(and_(Annotation.annotationname == _annotationname, Annotation.isactive==True)).first()[0]
       
    #upsert
    @classmethod
    def saveannotations(cls, annots, _documentid, _documentversion, userinfo)->DefaultMethodResult:
        try:
            values = [{
                "annotationname": annot["name"],
                "documentid": _documentid,
                "documentversion": _documentversion,
                "annotation": annot["xml"],
                "pagenumber": annot["page"],
                "createdby": userinfo,
                "isactive": True
            } for annot in annots]
            insertstmt = insert(Annotation).values(values)
            updatestmt = insertstmt.on_conflict_do_update(index_elements=[Annotation.annotationname], set_={"annotation": insertstmt.excluded.annotation,"updatedby":userinfo,"updated_at":datetime.now()})
            db.session.execute(updatestmt)     
            db.session.commit() 
            return DefaultMethodResult(True, 'Annotation added', [annot["name"] for annot in annots])
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()  
        
    @classmethod
    def deactivateannotation(cls, _annotationname, _documentid, _documentversion, userinfo)->DefaultMethodResult:
        db.session.query(Annotation).filter(Annotation.annotationname == _annotationname, Annotation.documentid == _documentid, Annotation.documentversion == _documentversion).update({"isactive": False, "updated_at": datetime.now(), "updatedby": userinfo}, synchronize_session=False)
        db.session.commit()
        return DefaultMethodResult(True,'Annotation deactivated',_annotationname)

class AnnotationSchema(ma.Schema):
    class Meta:
        fields = ('annotationid', 'annotationname', 'documentid', 'documentversion', 'annotation', 'pagenumber', 'isactive', 'createdby', 'created_at', 'updatedby', 'updated_at')
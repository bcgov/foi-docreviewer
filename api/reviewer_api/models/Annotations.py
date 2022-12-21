from .db import  db, ma
from .default_method_result import DefaultMethodResult
from sqlalchemy import or_, and_
from sqlalchemy.dialects.postgresql import JSON, insert
from datetime import datetime

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

    @classmethod
    def getannotations(cls, _documentid, _documentversion):
        annotation_schema = AnnotationSchema(many=True)
        query = db.session.query(Annotation).filter(and_(Annotation.documentid == _documentid, Annotation.documentversion == _documentversion, Annotation.isactive==True)).order_by(Annotation.annotationid.asc()).all()
        return annotation_schema.dump(query)

    #upsert
    @classmethod
    def saveannotation(cls, _annotationname, _documentid, _documentversion, _annotation, _pagenumber, userinfo)->DefaultMethodResult:
        # newannotation = Annotation(annotationname=_annotationname, documentid=_documentid, documentversion=_documentversion, annotation=_annotation, pagenumber=_pagenumber, createdby=userinfo)
        # db.session.add(newannotation)
        # db.session.commit()
        # return DefaultMethodResult(True,'Annotation added',newannotation.annotationid)

        insertstmt = insert(Annotation).values(
                                            annotationname=_annotationname,
                                            documentid=_documentid,
                                            documentversion=_documentversion,
                                            annotation=_annotation,
                                            pagenumber=_pagenumber,
                                            createdby=userinfo,
                                            isactive=True
                                        )
        updatestmt = insertstmt.on_conflict_do_update(index_elements=[Annotation.annotationname], set_={"annotation": _annotation,"updatedby":userinfo,"updated_at":datetime.now()})
        db.session.execute(updatestmt)               
        db.session.commit()   
        return DefaultMethodResult(True, 'Annotation added', _annotationname)

    # @classmethod
    # def updateannotation(cls, _annotationname, _documentid, _documentversion, _annotation, userinfo)->DefaultMethodResult:
    #     db.session.query(Annotation).filter(Annotation.annotationname == _annotationname, Annotation.documentid == _documentid, Annotation.documentversion == _documentversion).update({"annotation": _annotation, "updated_at": datetime.now(), "updatedby": userinfo}, synchronize_session=False)
    #     db.session.commit()
    #     return DefaultMethodResult(True,'Annotation updated',_annotationname)

    @classmethod
    def deactivateannotation(cls, _annotationname, _documentid, _documentversion, userinfo)->DefaultMethodResult:
        db.session.query(Annotation).filter(Annotation.annotationname == _annotationname, Annotation.documentid == _documentid, Annotation.documentversion == _documentversion).update({"isactive": False, "updated_at": datetime.now(), "updatedby": userinfo}, synchronize_session=False)
        db.session.commit()
        return DefaultMethodResult(True,'Annotation deactivated',_annotationname)

class AnnotationSchema(ma.Schema):
    class Meta:
        fields = ('annotationid', 'annotationname', 'documentid', 'documentversion', 'annotation', 'pagenumber', 'isactive', 'createdby', 'created_at', 'updatedby', 'updated_at')
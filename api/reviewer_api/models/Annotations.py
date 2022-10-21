from .db import  db, ma
from .default_method_result import DefaultMethodResult
from sqlalchemy import or_, and_
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime as datetime2

class Annotation(db.Model):
    __tablename__ = 'Annotations' 
    # Defining the columns
    annotationid = db.Column(db.Integer, primary_key=True,autoincrement=True)
    documentid = db.Column(db.Integer, db.ForeignKey('Documents.documentid'))
    documentversion = db.Column(db.Integer, db.ForeignKey('Documents.version'))
    annotation = db.Column(JSON, unique=False, nullable=False)
    pagenumber = db.Column(db.Integer, nullable=False)
    createdby = db.Column(JSON, unique=False, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime2.now)

    @classmethod
    def getannotations(cls, documentid, documentversion):
        annotation_schema = AnnotationSchema(many=True)
        query = db.session.query(Annotation).filter_by(and_(documentid = documentid, documentversion = documentversion)).order_by(Annotation.annotationid.asc()).all()
        return annotation_schema.dump(query)

    @classmethod
    def saveannotation(cls, _documentid, _documentversion, _annotation, _pagenumber, _createdby)->DefaultMethodResult:        
        newannotation = Annotation(documentid=_documentid, documentversion=_documentversion, annotation=_annotation, pagenumber=_pagenumber, createdby=_createdby)
        db.session.add(newannotation)
        db.session.commit()               
        return DefaultMethodResult(True,'Annotation added',newannotation.annotationid)

class AnnotationSchema(ma.Schema):
    class Meta:
        fields = ('annotationid', 'documentid', 'documentversion', 'annotation', 'pagenumber', 'createdby', 'created_at')
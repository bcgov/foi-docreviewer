from .db import  db, ma
from .default_method_result import DefaultMethodResult
from sqlalchemy import or_, and_
from sqlalchemy.dialects.postgresql import JSON, insert
from datetime import datetime
from sqlalchemy.sql.schema import ForeignKey, ForeignKeyConstraint
from reviewer_api.models.Annotations import Annotation
import logging
from sqlalchemy import text

class AnnotationSection(db.Model):
    __tablename__ = 'AnnotationSections'
    # Defining the columns
    id = db.Column(db.Integer, primary_key=True,autoincrement=True)
    foiministryrequestid =db.Column(db.Integer, nullable=True)
    section = db.Column(JSON, unique=False, nullable=False)
    createdby = db.Column(JSON, unique=False, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updatedby = db.Column(JSON, unique=False, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True)

    annotationname =db.Column(db.Integer, ForeignKey('Annotations.annotationname'))
    
    @classmethod
    def savesection(cls, _foiministryrequestid, _annotationname, _section, userinfo)->DefaultMethodResult:
        try:
            insertstmt = insert(AnnotationSection).values(
                                            foiministryrequestid = _foiministryrequestid,
                                            annotationname = _annotationname,
                                            section = _section,
                                            createdby = userinfo                                            
                                        )
            updatestmt = insertstmt.on_conflict_do_update(index_elements=[AnnotationSection.annotationname], set_={"section": _section,"updatedby":userinfo,"updated_at":datetime.now()})
            db.session.execute(updatestmt)               
            db.session.commit() 
            return DefaultMethodResult(True, 'Annotation Sections are saved', _annotationname)  
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()


    @classmethod
    def getsectionmapping(cls, documentid, documentversion):  
        mapping = []
        try:              
            sql = """select as2.annotationname  as "sectionannotationname", 
                        cast("section"  AS json) ->> 'redactannotation' as redactannotation,
                        cast("section"  AS json) ->> 'ids' as ids
                        from "AnnotationSections" as2, "Annotations" a  where  as2.annotationname  = a.annotationname 
                           and a.documentid = :documentid and a.documentversion = :documentversion;
                    """
            rs = db.session.execute(text(sql), {'documentid': documentid, 'documentversion': documentversion})
        
            for row in rs:
                mapping.append({"sectionannotationname":row["sectionannotationname"], "redactannotation":row["redactannotation"], "ids": row["ids"]})
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()
        return mapping

    @classmethod
    def get_by_annotationame(cls, _annotationname):
        annotation_section_schema = AnnotationSectionSchema(many=False)
        query = db.session.query(AnnotationSection).filter(and_(AnnotationSection.annotationname == _annotationname)).first()
        return annotation_section_schema.dump(query)

    @classmethod
    def get_by_ministryid(cls, ministryrequestid):
        annotation_section_schema = AnnotationSectionSchema(many=True)
        query = db.session.query(AnnotationSection).filter(and_(AnnotationSection.foiministryrequestid == ministryrequestid)).all()
        return annotation_section_schema.dump(query)

      
   
class AnnotationSectionSchema(ma.Schema):
    class Meta:
        fields = ('annotationname', 'foiministryrequestid', 'section', 'id', 'createdby', 'created_at', 'updatedby', 'updated_at')
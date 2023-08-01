from .db import  db, ma
from .default_method_result import DefaultMethodResult
from sqlalchemy import or_, and_
from sqlalchemy.orm import aliased
from sqlalchemy.dialects.postgresql import JSON, insert
from sqlalchemy.sql.expression import cast
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
    def savesections(cls, annots, _foiministryrequestid, userinfo)->DefaultMethodResult:
        try:
            values = [{
                "foiministryrequestid": _foiministryrequestid,
                "annotationname": annot["name"],
                "section": annot["sectionsschema"],
                "createdby": userinfo
            } for annot in annots]
            insertstmt = insert(AnnotationSection).values(values)
            updatestmt = insertstmt.on_conflict_do_update(index_elements=[AnnotationSection.annotationname], set_={"section": insertstmt.excluded.section,"updatedby":userinfo,"updated_at":datetime.now()})
            db.session.execute(updatestmt)               
            db.session.commit() 
            return DefaultMethodResult(True, 'Annotation Sections are saved', [annot["name"] for annot in annots])
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
                           and a.isactive = true and a.documentid = :documentid and a.documentversion = :documentversion;
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
    def getsectionmappingbyrequestid(cls, ministryrequestid):
        mapping = []
        try:
            sql = """select as2.annotationname  ,
                        cast("section"  AS json) ->> 'redactannotation' as redactannotation,
                        cast("section"  AS json) ->> 'ids' as ids
                        from "AnnotationSections" as2, "Annotations" a
                        join (select distinct on (d.documentid) d.*
                            from  "Documents" d
                            where d.foiministryrequestid = :ministryrequestid
                            order by d.documentid, d.version desc) d
                        on (d.documentid = a.documentid and d.version = a.documentversion)
                        where  as2.annotationname  = a.annotationname
                           and a.isactive = true and as2.foiministryrequestid = :ministryrequestid;
                    """
            rs = db.session.execute(text(sql), {'ministryrequestid': ministryrequestid})

            for row in rs:
                mapping.append({"annotationname":row["redactannotation"], "sectionannotation":row["annotationname"], "ids": row["ids"]})
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()
        return mapping

    @classmethod
    def get_by_annotationame(cls, _annotationname):
        try:
            annotation_section_schema = AnnotationSectionSchema(many=False)
            query = db.session.query(AnnotationSection).filter(and_(AnnotationSection.annotationname == _annotationname)).first()
            return annotation_section_schema.dump(query)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def get_by_ministryid(cls, ministryrequestid):
        try:
            annotation_section_schema = AnnotationSectionSchema(many=True)
            redaction = aliased(Annotation)
            query = db.session.query(AnnotationSection).join(
                Annotation, Annotation.annotationname == AnnotationSection.annotationname
            ).join(
                redaction, redaction.annotationname == cast(AnnotationSection.section, JSON)['redactannotation'].astext
            ).filter(and_(AnnotationSection.foiministryrequestid == ministryrequestid, Annotation.isactive == True, redaction.isactive == True)).all()
            return annotation_section_schema.dump(query)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def getredactedsectionsbyrequest(cls, ministryrequestid):
        try:
            sql = '''select section from public."Sections" where sectionid in
                        (select distinct (json_array_elements((as1.section::json->>'ids')::json)->>'id')::integer
                        from public."AnnotationSections" as1
                        join public."Annotations" a on a.annotationname = as1.annotationname
                        where foiministryrequestid = :ministryrequestid
                        and a.isactive = true)
                     and sectionid != 25
                     order by sortorder'''
            rs = db.session.execute(text(sql), {'ministryrequestid': ministryrequestid})
            sectionstring = ""
            for row in rs:
                sectionstring = sectionstring + row["section"] + ', '
            sectionstring = sectionstring[:-2]
            return sectionstring
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()


class AnnotationSectionSchema(ma.Schema):
    class Meta:
        fields = ('annotationname', 'foiministryrequestid', 'section', 'id', 'createdby', 'created_at', 'updatedby', 'updated_at')
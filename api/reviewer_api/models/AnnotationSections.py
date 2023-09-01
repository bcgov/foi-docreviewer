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
from reviewer_api.utils.util import split, getbatchconfig
import json

class AnnotationSection(db.Model):
    __tablename__ = 'AnnotationSections'
    # Defining the columns
    id = db.Column(db.Integer, primary_key=True,autoincrement=True)
    version = db.Column(db.Integer, primary_key=True, nullable=False)
    foiministryrequestid =db.Column(db.Integer, nullable=True)
    section = db.Column(JSON, unique=False, nullable=False)
    createdby = db.Column(JSON, unique=False, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updatedby = db.Column(JSON, unique=False, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True)
    isactive = db.Column(db.Boolean, unique=False, nullable=False)
    annotationname =db.Column(db.Integer, ForeignKey('Annotations.annotationname'))

    
    @classmethod
    def __getsectionkey(cls, _annotationname):
        try:
            return db.session.query(AnnotationSection.id, AnnotationSection.version).filter(and_(AnnotationSection.annotationname == _annotationname)).order_by(AnnotationSection.version.desc()).first()
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def __getbulksectionkey(cls, _annotationnames):
        apks = {}
        try:
            sql = """select distinct on (annotationname)  "annotationname", "version", id  
               from "AnnotationSections" as2 where annotationname IN :annotationnames
               order by annotationname, version desc;"""
            rs = db.session.execute(text(sql), {'annotationnames': tuple(_annotationnames)})
            for row in rs:
                apks[row['annotationname']] = {"id": row['id'], "version": row['version']}
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()
        return apks

    @classmethod
    def savesections(cls, annots, _foiministryrequestid, userinfo)-> DefaultMethodResult:
        begin, size, limit = getbatchconfig()
        if len(annots) > 0 and len(annots) < begin:
            return cls.__chunksavesections(annots, _foiministryrequestid, userinfo)
        elif len(annots) >= begin and len(annots) <= limit:
            return cls.__bulksavesections(annots, _foiministryrequestid, userinfo, size)
        else:
            return DefaultMethodResult(False, 'Invalid Annotation Section Request',  -1)


    @classmethod
    def __chunksavesections(cls, annots, _foiministryrequestid, userinfo)->DefaultMethodResult:
        successections = []
        failedsections = []
        try:
            for annot in annots:
                resp = cls.__savesection(annot, _foiministryrequestid, userinfo)
                if resp.success == True:
                    successections.append(annot["name"])    
                else:
                    failedsections.append(annot["name"])
            if len(failedsections) < 1:
                return DefaultMethodResult(True, 'Annotation sections are added', ','.join(successections))
            else:
                return DefaultMethodResult(True, 'Annotation sections are failed', ','.join(failedsections))
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def __bulksavesections(cls, annots, _foiministryrequestid, userinfo, size=100)->DefaultMethodResult:
        idxannots  = []
        try:
            wkannots =  split(annots,  size) 
            for wkannot in wkannots:
                annotnames = [d['name'] for d in wkannot]
                _pkvsections = cls.__getbulksectionkey(annotnames) 
                if _pkvsections not in (None, {}):
                    cls.__bulknewsections(wkannot, _pkvsections, _foiministryrequestid, userinfo)   
                    cls.__bulkdeactivatesections(annotnames, userinfo)
                    idxannots.extend(annotnames)
            return DefaultMethodResult(True, 'Annotations added',  ','.join(idxannots))
        except Exception as ex:
            logging.error(ex)

    @classmethod
    def __savesection(cls, annot, _foiministryrequestid, userinfo) -> DefaultMethodResult:
        sectkey = cls.__getsectionkey(annot["name"])
        if sectkey is None:
            return cls.__newsection(annot, _foiministryrequestid, userinfo)
        else:
            return cls.__updatesection(annot, _foiministryrequestid, userinfo, sectkey[0], sectkey[1])

    @classmethod
    def __newsection(cls, annot, _foiministryrequestid, userinfo) -> DefaultMethodResult:
        try:
            values = [{
                "annotationname": annot["name"],
                "foiministryrequestid": _foiministryrequestid,
                "section": annot["sectionsschema"],
                "version": 1,
                "createdby": userinfo,
                "isactive": True
            }]
            insertstmt = insert(AnnotationSection).values(values)
            upsertstmt = insertstmt.on_conflict_do_update(index_elements=[AnnotationSection.annotationname, AnnotationSection.version], set_={"isactive": False,"updatedby":userinfo,"updated_at":datetime.now()}).returning(AnnotationSection.isactive, AnnotationSection.id, AnnotationSection.version)
            sectproxy = db.session.execute(upsertstmt)
            result = [dict(row) for row in sectproxy] 
            db.session.commit() 
            if len(result) > 0:
                idxsect =  result[0]
                if idxsect['isactive'] == False:
                    return cls.__updatesection(annot, _foiministryrequestid, userinfo, idxsect['id'], idxsect['version'])
            return DefaultMethodResult(True, 'Annotation Sections are added', annot["name"])
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close() 

    @classmethod
    def __bulknewsections(cls, annots, _pkvannots, _foiministryrequestid, userinfo):
        datalist = []
        idxannots = []
        try:
            for annot in annots:    
                pkkey = _pkvannots[annot["name"]]
                datalist.append({
                "annotationname": annot["name"],
                "foiministryrequestid": _foiministryrequestid,
                "section": annot["sectionsschema"],
                "createdby": userinfo,
                "version": pkkey['version'] + 1,
                "isactive": True
                })
                idxannots.append(annot["name"])
            db.session.bulk_insert_mappings(AnnotationSection, datalist)
            db.session.commit()             
            return idxannots
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def __updatesection(cls, annot, _foiministryrequestid, userinfo, id= None, version=None) -> DefaultMethodResult:
        try:
            if id is None or version is None:
                return DefaultMethodResult(True, 'Unable to Save Annotation Section', annot["name"])
            cls.__deactivatesection(annot["name"], userinfo)
            values = [{
                "id" : id,
                "annotationname": annot["name"],
                "foiministryrequestid": _foiministryrequestid,
                "section": annot["sectionsschema"],   
                "createdby": userinfo,
                "isactive": True,
                "version": version + 1
            }]
            insertstmt = insert(AnnotationSection).values(values)
            secttmt = insertstmt.on_conflict_do_nothing()
            db.session.execute(secttmt)    
            db.session.commit() 
            return DefaultMethodResult(True, 'Annotation sections are updated', annot["name"])
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()  

    @classmethod
    def __deactivatesection(cls, _annotationname, userinfo)->DefaultMethodResult:
        try:
            db.session.query(AnnotationSection).filter(AnnotationSection.annotationname == _annotationname).update({"isactive": False, "updated_at": datetime.now(), "updatedby": userinfo}, synchronize_session=False)
            db.session.commit()
            return DefaultMethodResult(True,'Annotation Sections are  deactivated',_annotationname)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def __bulkdeactivatesections(cls, idxannots, userinfo)->DefaultMethodResult:
        try:
            sql = """update "AnnotationSections" a set isactive  = false, updatedby = :userinfo, updated_at=now() 
                    from (select distinct on (annotationname)  "annotationname", "version", id  
                    from "AnnotationSections"  where annotationname in :idxannots
                    order by annotationname, version desc) b  
                    where a.annotationname = b.annotationname
                    and a."version" < b.version
                    and a.isactive = true;"""
            db.session.execute(text(sql), {'idxannots': tuple(idxannots), 'userinfo': json.dumps(userinfo)})
            db.session.commit()
            return DefaultMethodResult(True, 'Annotation sections are updated', ','.join(idxannots))
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def getsectionmapping(cls, documentid, documentversion):  
        mapping = []
        try:              
            sql = """select as2.annotationname  as "sectionannotationname",
                        cast("section"  AS json) ->> 'redactannotation' as redactannotation,
                        cast("section"  AS json) ->> 'ids' as ids
                        from "AnnotationSections" as2, "Annotations" a  where  as2.annotationname  = a.annotationname and as2.isactive = true 
                           and a.isactive = true and a.documentid = :documentid and a.documentversion = :documentversion;
                    """
            rs = db.session.execute(text(sql), {'documentid': documentid, 'documentversion': documentversion})
        
            for row in rs:
                mapping.append({"sectionannotationname":row["sectionannotationname"], "redactannotation":row["redactannotation"], "ids": row["ids"]})
        except Exception as ex:
            logging.error(ex)
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
                        where  as2.annotationname  = a.annotationname and a.isactive = true 
                        and as2.foiministryrequestid = :ministryrequestid and as2.isactive  = true;
                    """
            rs = db.session.execute(text(sql), {'ministryrequestid': ministryrequestid})

            for row in rs:
                mapping.append({"annotationname":row["redactannotation"], "sectionannotation":row["annotationname"], "ids": row["ids"]})
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()
        return mapping

    @classmethod
    def get_by_annotationame(cls, _annotationname):
        try:
            annotation_section_schema = AnnotationSectionSchema(many=False)
            query = db.session.query(AnnotationSection).filter(and_(AnnotationSection.annotationname == _annotationname, AnnotationSection.isactive == True)).first()
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
            ).filter(and_(AnnotationSection.foiministryrequestid == ministryrequestid, AnnotationSection.isactive == True, Annotation.isactive == True, redaction.isactive == True)).all()
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
                        join public."Documents" d on d.documentid = a.documentid
                        join public."DocumentMaster" dm on dm.documentmasterid = d.documentmasterid
                        left join public."DocumentDeleted" dd on dm.filepath ilike dd.filepath || '%'
                        where as1.foiministryrequestid = :ministryrequestid and as1.isactive  = true
                        and (dd.deleted is null or dd.deleted is false)
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

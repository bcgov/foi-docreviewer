from .db import  db, ma
from .default_method_result import DefaultMethodResult
from sqlalchemy import or_, and_, text
from sqlalchemy.dialects.postgresql import JSON, insert
from datetime import datetime
from sqlalchemy.orm import relationship, backref, aliased
import logging

class Annotation(db.Model):
    __tablename__ = 'Annotations'
    # Defining the columns
    annotationid = db.Column(db.Integer, primary_key=True,autoincrement=True)
    version = db.Column(db.Integer, primary_key=True, nullable=False)
    annotationname = db.Column(db.String(120), unique=False, nullable=False)
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
    redactionlayerid = db.Column(db.Integer, db.ForeignKey('RedactionLayers.redactionlayerid'))
    redactionlayer = relationship("RedactionLayer", backref=backref("RedactionLayers"), uselist=False)


    @classmethod
    def getannotations(cls, _documentid, _documentversion):
        try:
            annotation_schema = AnnotationSchema(many=True)
            query = db.session.query(Annotation).filter(and_(Annotation.documentid == _documentid, Annotation.documentversion == _documentversion, Annotation.isactive==True)).order_by(Annotation.annotationid.asc()).all()
            return annotation_schema.dump(query)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def getrequestannotations(cls, ministryrequestid, mappedlayerids):
        sql = '''select a.*
                from "Annotations" a
                join (select distinct on (d.documentid) d.*
					  from  "Documents" d
                      where d.foiministryrequestid = :ministryrequestid
					  order by d.documentid, d.version desc) d
				on (d.documentid = a.documentid and d.version = a.documentversion)
                join "DocumentMaster" dm on dm.documentmasterid = d.documentmasterid
                left join "DocumentDeleted" dd on dm.filepath ilike dd.filepath || '%'
                where d.foiministryrequestid = :ministryrequestid
                and (dd.deleted is false or dd.deleted is null)
                and a.redactionlayerid in :_mappedlayerids
                and a.isactive = true
            '''
        rs = db.session.execute(text(sql), {'ministryrequestid': ministryrequestid, '_mappedlayerids':tuple(mappedlayerids)})
        db.session.close()
        return [{
            'annotationid': row['annotationid'],
            'annotationname': row['annotationname'],
            'documentid': row['documentid'],
            'documentversion': row['documentversion'],
            'annotation': row['annotation'],
            'pagenumber': row['pagenumber'],
            'isactive': row['isactive'],
            'createdby': row['createdby'],
            'created_at': row['created_at'],
            'updatedby': row['updatedby'],
            'updated_at': row['updated_at']
        } for row in rs]

    @classmethod
    def getrequestdivisionannotations(cls, ministryrequestid, divisionid):
        sql = '''
                select a.*
                from "Annotations" a
                join (
                    select distinct on (d.documentid) d.*
					from  "Documents" d
                    where d.foiministryrequestid = :ministryrequestid
					order by d.documentid, d.version desc
                ) d on (d.documentid = a.documentid and d.version = a.documentversion)
				inner join "DocumentMaster" dm on dm.documentmasterid = d.documentmasterid or dm.processingparentid = d.documentmasterid
                inner join "DocumentAttributes" da
                    on (da.documentmasterid = dm.documentmasterid or da.documentmasterid = dm.processingparentid)
					and da.isactive = true
					and (da.attributes ->> 'divisions')::jsonb @> '[{"divisionid": :divisionid}]'
					and a.isactive = true
            '''
        rs = db.session.execute(text(sql), {'ministryrequestid': ministryrequestid, 'divisionid': divisionid})
        db.session.close()
        return [{
            'annotationid': row['annotationid'],
            'annotationname': row['annotationname'],
            'documentid': row['documentid'],
            'documentversion': row['documentversion'],
            'annotation': row['annotation'],
            'pagenumber': row['pagenumber'],
            'isactive': row['isactive'],
            'createdby': row['createdby'],
            'created_at': row['created_at'],
            'updatedby': row['updatedby'],
            'updated_at': row['updated_at']
        } for row in rs]

    @classmethod
    def getredactionsbypage(cls, _documentid, _documentversion, _pagenum, redactionlayerid):
        try:
            annotation_schema = AnnotationSchema(many=True)
            query = db.session.query(Annotation).filter(
                and_(
                    Annotation.documentid == _documentid,
                    Annotation.documentversion == _documentversion,
                    Annotation.isactive==True,
                    Annotation.pagenumber == _pagenum-1,
                    Annotation.redactionlayerid == redactionlayerid,
                    Annotation.annotation.ilike('%<redact %')
                )).order_by(Annotation.annotationid.asc()).all()
            return annotation_schema.dump(query)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def getannotationinfo(cls, _documentid, _documentversion):
        try:
            annotation_schema = AnnotationSchema(many=True)
            query = db.session.query(Annotation.annotationname).filter(and_(Annotation.documentid == _documentid, Annotation.documentversion == _documentversion, Annotation.isactive==True)).order_by(Annotation.annotationid.asc()).all()
            return annotation_schema.dump(query)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    
        
    @classmethod
    def getannotationid(cls, _annotationname):
        try:
            return db.session.query(Annotation.annotationid).filter(and_(Annotation.annotationname == _annotationname, Annotation.isactive==True)).first()[0]
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def getannotationkey(cls, _annotationname):
        try:
            return db.session.query(Annotation.annotationid, Annotation.version).filter(and_(Annotation.annotationname == _annotationname)).order_by(Annotation.version.desc()).first()
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def saveannotations(cls, annots, redactionlayerid, userinfo)->DefaultMethodResult:
        successannots = []
        failedannots = []
        try:
            for annot in annots:
                resp = cls.saveannotation(annot, redactionlayerid, userinfo)
                if resp is not None and resp.success == True:
                    successannots.append(annot["name"])    
                else:
                    failedannots.append(annot["name"])    
            if len(failedannots) < 1:
                return DefaultMethodResult(True, 'Annotations added',  ','.join(successannots))
            else:
                return DefaultMethodResult(True, 'Annotations failed',  ','.join(failedannots))
        except Exception as ex:
            logging.error(ex)
            raise ex
        
    @classmethod
    def saveannotation(cls, annot, redactionlayerid, userinfo) -> DefaultMethodResult:
        annotkey = cls.getannotationkey(annot["existingid"]) if annot["existingid"] is not None else cls.getannotationkey(annot["name"])
        print("\nannotkey:",annotkey)
        if annotkey is None:
            return cls.newannotation(annot, redactionlayerid, userinfo)
        else:
            return cls.updateannoation(annot, redactionlayerid, userinfo, annotkey[0], annotkey[1])
             

    @classmethod
    def newannotation(cls, annot, redactionlayerid, userinfo) -> DefaultMethodResult:
        try:
            values = [{
                "annotationname": annot["name"],
                "documentid": annot["docid"],
                "documentversion": 1,
                "annotation": annot["xml"],
                "pagenumber": annot["page"],
                "createdby": userinfo,
                "isactive": True,
                "version": 1,
                "redactionlayerid" : redactionlayerid
            }]
            insertstmt = insert(Annotation).values(values)
            upsertstmt = insertstmt.on_conflict_do_update(index_elements=[Annotation.annotationname, Annotation.version], set_={"isactive": False,"updatedby":userinfo,"updated_at":datetime.now()}).returning(Annotation.isactive, Annotation.annotationid, Annotation.version)
            annotproxy = db.session.execute(upsertstmt)
            result = [dict(row) for row in annotproxy] 
            db.session.commit() 
            if len(result) > 0:
                idxannot =  result[0]
                if idxannot['isactive'] == False:
                    return cls.updateannoation(annot, redactionlayerid, userinfo, idxannot['annotationid'], idxannot['version'])
            return DefaultMethodResult(True, 'Annotation added', annot["name"])
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()   

    @classmethod
    def updateannoation(cls, annot, redactionlayerid, userinfo, id=None, version=None) -> DefaultMethodResult:
        try:
            if id is None or version is None:
                return DefaultMethodResult(True, 'Unable to Save Annotation', annot["name"])
            existingannotationname = annot["existingid"] if annot["existingid"] is not None else annot["name"]
            cls.deactivateannotation(existingannotationname, annot["docid"], 1, userinfo)
            values = [{
                "annotationid" : id,
                "annotationname": annot["name"],
                "documentid": annot["docid"],
                "documentversion": annot["docversion"],
                "annotation": annot["xml"],
                "pagenumber": annot["page"],
                "createdby": userinfo,
                "isactive": True,
                "version": version + 1,
                "redactionlayerid" : redactionlayerid
            }]
            insertstmt = insert(Annotation).values(values)
            annotstmt = insertstmt.on_conflict_do_nothing()
            db.session.execute(annotstmt)    
            db.session.commit() 
            return DefaultMethodResult(True, 'Annotation updated', annot["name"])
        except Exception as ex:
            logging.error(ex)
            raise ex
        finally:
            db.session.close()  
        
    @classmethod
    def deactivateannotation(cls, _annotationname, _documentid, _documentversion, userinfo)->DefaultMethodResult:
        try:
            db.session.query(Annotation).filter(Annotation.annotationname == _annotationname, Annotation.documentid == _documentid, Annotation.documentversion == _documentversion).update({"isactive": False, "updated_at": datetime.now(), "updatedby": userinfo}, synchronize_session=False)
            db.session.commit()
            return DefaultMethodResult(True,'Annotation deactivated',_annotationname)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

class AnnotationSchema(ma.Schema):
    class Meta:
        fields = ('annotationid', 'annotationname', 'documentid', 'documentversion', 'annotation', 'pagenumber', 'redactionlayerid', 'redactionlayer.redactionlayerid', 'isactive', 'createdby', 'created_at', 'updatedby', 'updated_at')
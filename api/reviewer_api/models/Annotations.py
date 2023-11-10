from .db import db, ma
from .default_method_result import DefaultMethodResult
from sqlalchemy import or_, and_, text
from sqlalchemy.dialects.postgresql import JSON, insert
from datetime import datetime
from sqlalchemy.orm import relationship, backref, aliased
import logging
import json
from reviewer_api.utils.util import split, getbatchconfig
from .Documents import Document
from .DocumentMaster import DocumentMaster


class Annotation(db.Model):
    __tablename__ = "Annotations"
    # Defining the columns
    annotationid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    version = db.Column(db.Integer, primary_key=True, nullable=False)
    annotationname = db.Column(db.String(120), unique=False, nullable=False)
    documentid = db.Column(db.Integer, db.ForeignKey("Documents.documentid"))
    documentversion = db.Column(db.Integer, db.ForeignKey("Documents.version"))
    annotation = db.Column(db.Text, unique=False, nullable=False)
    pagenumber = db.Column(db.Integer, nullable=False)
    isactive = db.Column(db.Boolean, unique=False, nullable=False)
    createdby = db.Column(JSON, unique=False, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updatedby = db.Column(JSON, unique=False, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True)

    sections = relationship(
        "AnnotationSection",
        primaryjoin="and_(Annotation.annotationname==AnnotationSection.annotationname)",
    )
    redactionlayerid = db.Column(
        db.Integer, db.ForeignKey("RedactionLayers.redactionlayerid")
    )
    redactionlayer = relationship(
        "RedactionLayer", backref=backref("RedactionLayers"), uselist=False
    )

    @classmethod
    def getannotations(cls, _documentid, _documentversion):
        try:
            annotation_schema = AnnotationSchema(many=True)
            query = (
                db.session.query(Annotation)
                .filter(
                    and_(
                        Annotation.documentid == _documentid,
                        Annotation.documentversion == _documentversion,
                        Annotation.isactive == True,
                    )
                )
                .order_by(Annotation.annotationid.asc())
                .all()
            )
            return annotation_schema.dump(query)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def getrequestannotations(cls, ministryrequestid, mappedlayerids):
        sql = """select a.*
                from "Annotations" a
                join (select distinct on (docs.documentid) docs.*
					  from  "Documents" docs
                      where docs.foiministryrequestid = :ministryrequestid
					  order by docs.documentid, docs.version desc) as d
				on (d.documentid = a.documentid and d.version = a.documentversion and d.foiministryrequestid = :ministryrequestid)
                join "DocumentMaster" dm on dm.documentmasterid = d.documentmasterid and dm.ministryrequestid = :ministryrequestid
                left join "DocumentDeleted" dd on dm.filepath ilike dd.filepath || '%' and dd.ministryrequestid = :ministryrequestid
                where d.foiministryrequestid = :ministryrequestid
                and (dd.deleted is false or dd.deleted is null)
                and a.redactionlayerid in :_mappedlayerids
                and a.isactive = true
            """
        rs = db.session.execute(
            text(sql),
            {
                "ministryrequestid": ministryrequestid,
                "_mappedlayerids": tuple(mappedlayerids),
            },
        )
        db.session.close()
        return [
            {
                "annotationid": row["annotationid"],
                "annotationname": row["annotationname"],
                "documentid": row["documentid"],
                "documentversion": row["documentversion"],
                "annotation": row["annotation"],
                "pagenumber": row["pagenumber"],
                "isactive": row["isactive"],
                "createdby": row["createdby"],
                "created_at": row["created_at"],
                "updatedby": row["updatedby"],
                "updated_at": row["updated_at"],
            }
            for row in rs
        ]

    @classmethod
    def get_request_annotations_pagination(
        cls, ministryrequestid, mappedlayerids, page, size
    ):
        _deleted = DocumentMaster.getdeleted(ministryrequestid)
        _replacedimages = DocumentMaster.filterreplacedimagefiles(ministryrequestid)
        _replacedotherfiles = DocumentMaster.filterreplacedfiles(ministryrequestid)
        _session = db.session
        _subquery_annotation = (
            _session.query(
                Annotation.pagenumber, Annotation.annotation, Document.documentid
            )
            .join(
                Document,
                and_(
                    Annotation.documentid == Document.documentid,
                    Document.documentmasterid.notin_(_deleted),
                    Document.documentmasterid.notin_(_replacedimages),
                    Document.documentmasterid.in_(_replacedotherfiles),
                    Document.foiministryrequestid == ministryrequestid,
                ),
            )
            .filter(
                Annotation.redactionlayerid.in_(mappedlayerids),
                Annotation.isactive == True,
            )
            .order_by(
                Document.documentid, Annotation.pagenumber, Annotation.annotationid
            )
        )
        result = _subquery_annotation.paginate(page=page, per_page=size)
        return result
    @classmethod
    def get_document_annotations(cls, ministryrequestid, mappedlayerids, documentid):
        try:
            sql = """
                    select a.*
                    from "Annotations" a
                    join (
                        select distinct on (docs.documentid) docs.*
                        from  "Documents" docs
                        where docs.foiministryrequestid = :ministryrequestid and docs.documentid = :documentid
                        order by docs.documentid, docs.version desc
                    ) as d on (d.documentid = a.documentid and d.version = a.documentversion and d.foiministryrequestid = :ministryrequestid)
                    inner join "DocumentMaster" dm on dm.documentmasterid = d.documentmasterid or dm.processingparentid = d.documentmasterid and dm.ministryrequestid = :ministryrequestid
                    where a.isactive = true and a.redactionlayerid in :_mappedlayerids
                """
            rs = db.session.execute(
                text(sql),
                {"ministryrequestid": ministryrequestid, "_mappedlayerids": tuple(mappedlayerids), "documentid": documentid},
            )
            return [
                row["annotation"]            
                for row in rs
            ]
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def getrequestdivisionannotations(cls, ministryrequestid, divisionid):
        sql = """
                select a.*
                from "Annotations" a
                join (
                    select distinct on (docs.documentid) docs.*
					from  "Documents" docs
                    where docs.foiministryrequestid = :ministryrequestid
					order by docs.documentid, docs.version desc
                ) as d on (d.documentid = a.documentid and d.version = a.documentversion)
				inner join "DocumentMaster" dm on dm.documentmasterid = d.documentmasterid or dm.processingparentid = d.documentmasterid
                inner join "DocumentAttributes" da
                    on (da.documentmasterid = dm.documentmasterid or da.documentmasterid = dm.processingparentid)
					and da.isactive = true
					and (da.attributes ->> 'divisions')::jsonb @> '[{"divisionid": :divisionid}]'
					and a.isactive = true
            """
        rs = db.session.execute(
            text(sql),
            {"ministryrequestid": ministryrequestid, "divisionid": divisionid},
        )
        db.session.close()
        return [
            {
                "annotationid": row["annotationid"],
                "annotationname": row["annotationname"],
                "documentid": row["documentid"],
                "documentversion": row["documentversion"],
                "annotation": row["annotation"],
                "pagenumber": row["pagenumber"],
                "isactive": row["isactive"],
                "createdby": row["createdby"],
                "created_at": row["created_at"],
                "updatedby": row["updatedby"],
                "updated_at": row["updated_at"],
            }
            for row in rs
        ]

    @classmethod
    def getredactionsbypage(
        cls, _documentid, _documentversion, _pagenum, redactionlayerid
    ):
        try:
            annotation_schema = AnnotationSchema(many=True)
            query = (
                db.session.query(Annotation)
                .filter(
                    and_(
                        Annotation.documentid == _documentid,
                        Annotation.documentversion == _documentversion,
                        Annotation.isactive == True,
                        Annotation.pagenumber == _pagenum - 1,
                        Annotation.redactionlayerid == redactionlayerid,
                        Annotation.annotation.ilike("%<redact %"),
                    )
                )
                .order_by(Annotation.annotationid.asc())
                .all()
            )
            return annotation_schema.dump(query)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def getannotationinfo(cls, _documentid, _documentversion):
        try:
            annotation_schema = AnnotationSchema(many=True)
            query = (
                db.session.query(Annotation.annotationname)
                .filter(
                    and_(
                        Annotation.documentid == _documentid,
                        Annotation.documentversion == _documentversion,
                        Annotation.isactive == True,
                    )
                )
                .order_by(Annotation.annotationid.asc())
                .all()
            )
            return annotation_schema.dump(query)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def getannotationid(cls, _annotationname):
        try:
            return (
                db.session.query(Annotation.annotationid)
                .filter(
                    and_(
                        Annotation.annotationname == _annotationname,
                        Annotation.isactive == True,
                    )
                )
                .first()[0]
            )
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def __getannotationkey(cls, _annotationname):
        try:
            return (
                db.session.query(Annotation.annotationid, Annotation.version)
                .filter(and_(Annotation.annotationname == _annotationname))
                .order_by(Annotation.version.desc())
                .first()
            )
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def __getbulkannotationkey(cls, _annotationnames):
        apks = {}
        try:
            sql = """select distinct on (annotationname)  "annotationname", "version", annotationid  
               from "Annotations"  where annotationname IN :annotationnames
               order by annotationname, version desc;"""
            rs = db.session.execute(
                text(sql), {"annotationnames": tuple(_annotationnames)}
            )
            for row in rs:
                apks[row["annotationname"]] = {
                    "annotationid": row["annotationid"],
                    "version": row["version"],
                }
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()
        return apks

    @classmethod
    def saveannotations(cls, annots, redactionlayerid, userinfo) -> DefaultMethodResult:
        begin, size, limit = getbatchconfig()
        if len(annots) > 0 and len(annots) < begin:
            return cls.__chunksaveannotations(annots, redactionlayerid, userinfo)
        elif len(annots) >= begin and len(annots) <= limit:
            return cls.__bulksaveannotations(annots, redactionlayerid, userinfo, size)
        else:
            return DefaultMethodResult(False, "Invalid Annotation Request", -1)

    @classmethod
    def __chunksaveannotations(
        cls, annots, redactionlayerid, userinfo
    ) -> DefaultMethodResult:
        successannots = []
        failedannots = []
        try:
            for annot in annots:
                resp = cls.__saveannotation(annot, redactionlayerid, userinfo)
                if resp is not None and resp.success == True:
                    successannots.append(annot["name"])
                else:
                    failedannots.append(annot["name"])
            if len(failedannots) < 1:
                return DefaultMethodResult(
                    True, "Annotations added", ",".join(successannots)
                )
            else:
                return DefaultMethodResult(
                    True, "Annotations failed", ",".join(failedannots)
                )
        except Exception as ex:
            logging.error(ex)

    @classmethod
    def __bulksaveannotations(
        cls, annots, redactionlayerid, userinfo, size=100
    ) -> DefaultMethodResult:
        idxannots = []
        try:
            wkannots = split(annots, size)
            for wkannot in wkannots:
                annotnames = [d["name"] for d in wkannot]
                _pkvannots = cls.__getbulkannotationkey(annotnames)
                cls.__bulknewannotations(
                    wkannot, _pkvannots, redactionlayerid, userinfo
                )
                cls.__bulkarchiveannotation(annotnames, redactionlayerid, userinfo)
                idxannots.extend(annotnames)
            return DefaultMethodResult(True, "Annotations added", ",".join(idxannots))
        except Exception as ex:
            logging.error(ex)

    @classmethod
    def __saveannotation(cls, annot, redactionlayerid, userinfo) -> DefaultMethodResult:
        annotkey = cls.__getannotationkey(annot["name"])
        if annotkey is None:
            return cls.__newannotation(annot, redactionlayerid, userinfo)
        else:
            return cls.__updateannotation(
                annot, redactionlayerid, userinfo, annotkey[0], annotkey[1]
            )

    @classmethod
    def __newannotation(cls, annot, redactionlayerid, userinfo) -> DefaultMethodResult:
        try:
            values = [
                {
                    "annotationname": annot["name"],
                    "documentid": annot["docid"],
                    "documentversion": 1,
                    "annotation": annot["xml"],
                    "pagenumber": annot["page"],
                    "createdby": userinfo,
                    "isactive": True,
                    "version": 1,
                    "redactionlayerid": redactionlayerid,
                }
            ]
            insertstmt = insert(Annotation).values(values)
            upsertstmt = insertstmt.on_conflict_do_update(
                index_elements=[
                    Annotation.annotationname,
                    Annotation.version,
                    Annotation.redactionlayerid,
                ],
                set_={
                    "isactive": False,
                    "updatedby": userinfo,
                    "updated_at": datetime.now(),
                },
            ).returning(
                Annotation.isactive, Annotation.annotationid, Annotation.version
            )
            annotproxy = db.session.execute(upsertstmt)
            result = [dict(row) for row in annotproxy]
            db.session.commit()
            if len(result) > 0:
                idxannot = result[0]
                if idxannot["isactive"] == False:
                    return cls.__updateannotation(
                        annot,
                        redactionlayerid,
                        userinfo,
                        idxannot["annotationid"],
                        idxannot["version"],
                    )
            return DefaultMethodResult(True, "Annotation added", annot["name"])
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def __bulknewannotations(cls, annots, _pkvannots, redactionlayerid, userinfo):
        datalist = []
        idxannots = []
        try:
            for annot in annots:
                pkkey = (
                    _pkvannots[annot["name"]] if _pkvannots not in (None, {}) else None
                )
                datalist.append(
                    {
                        "annotationname": annot["name"],
                        "documentid": annot["docid"],
                        "documentversion": 1,
                        "annotation": annot["xml"],
                        "pagenumber": annot["page"],
                        "createdby": userinfo,
                        "isactive": True,
                        "redactionlayerid": redactionlayerid,
                        "version": pkkey["version"] + 1
                        if pkkey is not None and "version" in pkkey
                        else 1,
                        "annotationid": pkkey["annotationid"]
                        if pkkey is not None and "annotationid" in pkkey
                        else None,
                    }
                )
                idxannots.append(annot["name"])
            db.session.bulk_insert_mappings(Annotation, datalist)
            db.session.commit()
            return idxannots
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def __updateannotation(
        cls, annot, redactionlayerid, userinfo, id=None, version=None
    ) -> DefaultMethodResult:
        try:
            if id is None or version is None:
                return DefaultMethodResult(
                    True, "Unable to Save Annotation", annot["name"]
                )
            values = [
                {
                    "annotationid": id,
                    "annotationname": annot["name"],
                    "documentid": annot["docid"],
                    "documentversion": annot["docversion"],
                    "annotation": annot["xml"],
                    "pagenumber": annot["page"],
                    "createdby": userinfo,
                    "isactive": True,
                    "version": version + 1,
                    "redactionlayerid": redactionlayerid,
                }
            ]
            insertstmt = insert(Annotation).values(values)
            annotstmt = insertstmt.on_conflict_do_nothing()
            db.session.execute(annotstmt)
            db.session.commit()
            cls.__archiveannotation(annot["name"], redactionlayerid, userinfo)
            return DefaultMethodResult(True, "Annotation updated", annot["name"])
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def __archiveannotation(
        cls, _annotationname, redactionlayerid, userinfo
    ) -> DefaultMethodResult:
        return cls.__bulkarchiveannotation(
            [_annotationname], redactionlayerid, userinfo
        )

    @classmethod
    def __bulkarchiveannotation(
        cls, idxannots, redactionlayerid, userinfo
    ) -> DefaultMethodResult:
        try:
            sql = """update "Annotations" a set isactive  = false, updatedby = :userinfo, updated_at=now() 
                    from (select distinct on (annotationname)  "annotationname", "version", annotationid  
                    from "Annotations"  where annotationname in :idxannots 
                    and redactionlayerid = :redactionlayerid
                    order by annotationname, version desc) as b  
                    where a.annotationname = b.annotationname
                    and a."version" < b.version
                    and a.redactionlayerid = :redactionlayerid
                    and a.isactive = True"""
            db.session.execute(
                text(sql),
                {
                    "idxannots": tuple(idxannots),
                    "userinfo": json.dumps(userinfo),
                    "redactionlayerid": redactionlayerid,
                },
            )
            db.session.commit()
            return DefaultMethodResult(
                True, "Annotations are updated", ",".join(idxannots)
            )
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def bulkdeleteannotations(
        cls, idxannots, redactionlayerid, userinfo
    ) -> DefaultMethodResult:
        try:
            sql = """update "Annotations" a set isactive  = false, updatedby = :userinfo, updated_at=now()                      
                    where a.annotationname in :idxannots
                    and a.redactionlayerid = :redactionlayerid
                    and a.isactive = True"""
            db.session.execute(
                text(sql),
                {
                    "idxannots": tuple(idxannots),
                    "userinfo": json.dumps(userinfo),
                    "redactionlayerid": redactionlayerid,
                },
            )
            db.session.commit()
            return DefaultMethodResult(
                True, "Annotations are deleted", ",".join(idxannots)
            )
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def getredactionsbydocumentpages(cls, _documentid, _pages, redactionlayerid):
        try:
            annotation_schema = AnnotationSchema(many=True)
            query = (
                db.session.query(Annotation.documentid, Annotation.pagenumber)
                .filter(
                    and_(
                        Annotation.documentid == _documentid,
                        Annotation.isactive == True,
                        Annotation.pagenumber.in_(_pages),
                        Annotation.redactionlayerid == redactionlayerid,
                        Annotation.annotation.ilike("%<redact %"),
                    )
                )
                .order_by(Annotation.annotationid.asc())
                .all()
            )
            return annotation_schema.dump(query)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()


class AnnotationSchema(ma.Schema):
    class Meta:
        fields = (
            "annotationid",
            "annotationname",
            "documentid",
            "documentversion",
            "annotation",
            "pagenumber",
            "redactionlayerid",
            "redactionlayer.redactionlayerid",
            "isactive",
            "createdby",
            "created_at",
            "updatedby",
            "updated_at",
        )

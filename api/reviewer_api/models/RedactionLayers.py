from .db import db, ma
from .default_method_result import DefaultMethodResult
from datetime import datetime as datetime2
from sqlalchemy import or_, and_, text
import logging



class RedactionLayer(db.Model):
    __tablename__ = "RedactionLayers"
    # Defining the columns
    redactionlayerid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), unique=False, nullable=False)
    description = db.Column(db.String(255), unique=False, nullable=False)
    sortorder = db.Column(db.String(100), unique=False, nullable=True)
    isactive = db.Column(db.Boolean, unique=False, nullable=False)
    createdby = db.Column(db.String(120), unique=False, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime2.now)
    updatedby = db.Column(db.String(120), unique=False, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True)

    @classmethod
    def getall(cls, ministryrequestid):
        try:
            sql = """select rl.*, case when sq.count is null then 0 else sq.count end as count 
                        from public."RedactionLayers" rl left join (
                            select redactionlayerid as rlid, count(redactionlayerid) 
                            from public."Annotations" a
                            join public."Documents" d on d.documentid = a.documentid and d.foiministryrequestid = :ministryrequestid
                            join public."DocumentMaster" dm on dm.documentmasterid = d.documentmasterid and dm.ministryrequestid = :ministryrequestid
							left join public."DocumentDeleted" dd on dm.filepath ilike dd.filepath || '%' and dd.ministryrequestid = :ministryrequestid
                            where foiministryrequestid = :ministryrequestid and a.isactive = true
							and (dd.deleted is false or dd.deleted is null)
                            group by redactionlayerid
                        ) as sq on sq.rlid = rl.redactionlayerid
                    """
            rs = db.session.execute(text(sql), {"ministryrequestid": ministryrequestid})
            return [
                {
                    "redactionlayerid": row["redactionlayerid"],
                    "name": row["name"],
                    "description": row["description"],
                    "sortorder": row["sortorder"],
                    "count": row["count"],
                }
                for row in rs
            ]
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def getredlineredactionlayer(cls):
        try:
            layer_schema = RedactionLayerSchema(many=False)
            query = (
                db.session.query(RedactionLayer)
                .filter_by(isactive=True, name="Redline")
                .order_by(RedactionLayer.sortorder.desc())
                .first()
            )
            return layer_schema.dump(query)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

    @classmethod
    def getlayers(cls):
        try:
            layer_schema = RedactionLayerSchema(many=True)
            query = (
                db.session.query(RedactionLayer)
                .filter_by(isactive=True)
                .all()
            )
            return layer_schema.dump(query)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()


class RedactionLayerSchema(ma.Schema):
    class Meta:
        fields = ("redactionlayerid", "name", "description", "sortorder")

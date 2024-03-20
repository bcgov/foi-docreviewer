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
            sql = """select r.redactionlayerid, r."name", r.description, r.sortorder, count(as2.id) as count 
            from  "RedactionLayers" r left join "DocumentPageflags" as2 on  r.redactionlayerid = as2.redactionlayerid and as2.foiministryrequestid = :ministryrequestid 
            where  r.isactive = true 
            group by  r.redactionlayerid, as2.redactionlayerid
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

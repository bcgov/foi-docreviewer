from .db import  db, ma
from .default_method_result import DefaultMethodResult
from sqlalchemy import or_
from datetime import datetime as datetime2
import logging

class Section(db.Model):
    __tablename__ = 'Sections' 
    # Defining the columns
    sectionid = db.Column(db.Integer, primary_key=True,autoincrement=True)
    section = db.Column(db.String(255), unique=False, nullable=False)  
    description = db.Column(db.String(255), unique=False, nullable=False)    
    sortorder = db.Column(db.String(100), unique=False, nullable=True)
    isactive = db.Column(db.Boolean, unique=False, nullable=False)
    createdby = db.Column(db.String(120), unique=False, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime2.now)
    updatedby = db.Column(db.String(120), unique=False, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True)

    @classmethod
    def getall(cls):
        try:
            section_schema = SectionSchema(many=True)
            query = db.session.query(Section).filter_by(isactive=True).order_by(Section.sortorder.asc()).all()
            return section_schema.dump(query)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

class SectionSchema(ma.Schema):
    class Meta:
        fields = ('sectionid', 'section', 'description','sortorder')
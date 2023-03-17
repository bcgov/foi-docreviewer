from .db import  db, ma
from .default_method_result import DefaultMethodResult
from sqlalchemy import or_
from datetime import datetime as datetime2
from sqlalchemy import or_, and_

class Pageflag(db.Model):
    __tablename__ = 'Pageflags' 
    # Defining the columns
    pageflagid = db.Column(db.Integer, primary_key=True,autoincrement=True)
    name = db.Column(db.String(255), unique=False, nullable=False)  
    description = db.Column(db.String(255), unique=False, nullable=False)    
    sortorder = db.Column(db.String(100), unique=False, nullable=True)
    isactive = db.Column(db.Boolean, unique=False, nullable=False)
    createdby = db.Column(db.String(120), unique=False, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime2.now)
    updatedby = db.Column(db.String(120), unique=False, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True)

    @classmethod
    def getall(cls):
        pageflag_schema = PageflagSchema(many=True)
        query = db.session.query(Pageflag).filter_by(isactive=True).order_by(Pageflag.sortorder.asc()).all()
        return pageflag_schema.dump(query)
    

class PageflagSchema(ma.Schema):
    class Meta:
        fields = ('pageflagid', 'name', 'description','sortorder')
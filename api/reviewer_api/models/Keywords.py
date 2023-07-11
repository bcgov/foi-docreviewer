from .db import  db, ma
from .default_method_result import DefaultMethodResult
from sqlalchemy import or_
from datetime import datetime as datetime2
from sqlalchemy import or_, and_

class Keyword(db.Model):
    __tablename__ = 'Keywords' 
    # Defining the columns
    keywordid = db.Column(db.Integer, primary_key=True,autoincrement=True)
    keyword = db.Column(db.String(255), unique=False, nullable=False)  
    category = db.Column(db.String(255), unique=False, nullable=False)    
    version = db.Column(db.Integer, nullable=False)
    isactive = db.Column(db.Boolean, unique=False, nullable=False)
    createdby = db.Column(db.String(120), unique=False, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime2.now)
    updatedby = db.Column(db.String(120), unique=False, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True)

    @classmethod
    def getall(cls):
        keyword_schema = KeywordSchema(many=True)
        query = db.session.query(Keyword).filter_by(isactive=True).all()
        return keyword_schema.dump(query)
    

class KeywordSchema(ma.Schema):
    class Meta:
        fields = ('keywordid', 'version', 'keyword', 'category')
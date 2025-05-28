from sqlalchemy import Column, Integer, String, Text
from .db import  db, ma
import uuid
from datetime import datetime
from .default_method_result import DefaultMethodResult

class RedlineContent(db.Model):
    __tablename__ = 'redline_content'

    id = db.Column(Integer, primary_key=True, autoincrement=True)
    redlineid =  db.Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    ministryrequestid = db.Column(Integer, nullable=False)
    documentid = db.Column(Integer, nullable=False)
    type = db.Column(String(250), nullable=False)
    section = db.Column(String(100), nullable=True)
    content = db.Column(Text, nullable=True)
    category = db.Column(String(250), nullable=True)

    def __init__(self, redlineid,ministryrequestid, documentid, type, section=None, content=None, category=None, createdby=None):
        self.redlineid = redlineid
        self.ministryrequestid = ministryrequestid
        self.documentid = documentid
        self.type = type
        self.section = section
        self.content = content
        self.category = category
        self.createdat = datetime.utcnow()
        self.createdby = createdby

    @classmethod
    def save(self, dict_rows)-> DefaultMethodResult:       
        db.session.bulk_insert_mappings(RedlineContent,dict_rows)
        db.session.commit()

    def as_dict(self):
        return {
            "id": self.id,
            "redlineid": self.redlineid,
            "ministryrequestid": self.ministryrequestid,
            "documentid": self.documentid,
            "type": self.type,
            "section": self.section,
            "content": self.content,
            "category": self.category,
            "createdat": self.createdat,
            "createdby": self.createdby
        }
    
class RedlineContentSchema(ma.Schema):
    class Meta:
        fields = ('id',  'redlineid', 'ministryrequestid', 'documentid', 'type', 'section', 'content', 'category', 'createdat', 'createdby')   
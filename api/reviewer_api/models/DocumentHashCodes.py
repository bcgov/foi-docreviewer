from .db import  db, ma
from datetime import datetime as datetime2

class DocumentHashCodes(db.Model):
    __tablename__ = 'DocumentHashCodes'
    # Defining the columns
    documentid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    rank1hash = db.Column(db.String, nullable=False)
    rank2hash = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime2.now)

class DocumentHashCodesSchema(ma.Schema):
    class Meta:
        fields = ('documentid', 'rank1hash', 'rank2hash', 'created_at')
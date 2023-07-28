from .db import  db, ma
from .default_method_result import DefaultMethodResult
from sqlalchemy import func, and_
import logging

class OperatingTeamS3ServiceAccount(db.Model):
    __tablename__ = 'OperatingTeamS3ServiceAccounts' 
    # Defining the columns
    teamid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    usergroup = db.Column(db.String(120), unique=False, nullable=False)
    accesskey = db.Column(db.String(255), unique=False, nullable=False)
    secret = db.Column(db.String(255), unique=False, nullable=False)
    type = db.Column(db.String(120), unique=False, nullable=False)
    isactive = db.Column(db.Boolean, unique=False, nullable=False)

    @classmethod
    def getserviceaccount(cls, usergroup):
        try:
            s3account_schema = OperatingTeamS3ServiceAccountSchema(many=False)
            query = db.session.query(OperatingTeamS3ServiceAccount).filter(func.lower(OperatingTeamS3ServiceAccount.usergroup)==func.lower(usergroup), OperatingTeamS3ServiceAccount.isactive == True).first()
            return s3account_schema.dump(query)
        except Exception as ex:
            logging.error(ex)
        finally:
            db.session.close()

class OperatingTeamS3ServiceAccountSchema(ma.Schema):
    class Meta:
        fields = ('teamid', 'usergroup', 'accesskey', 'secret', 'type', 'isactive')
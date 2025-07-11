from sqlalchemy import Column, String
from .db import  db, ma

class BCGovIDIR(db.Model):
    __tablename__ = 'BCGovIDIRs'
    __table_args__ = {'schema': 'public'}

    sAMAccountName = Column(String, primary_key=True)

    @classmethod
    def fetch_by_samaccountnames(cls, names):
        """
        Fetch rows where sAMAccountName is in the provided list.
        :param names: List of sAMAccountName strings
        :return: List of BCGovIDIR objects
        """
        return db.session.query(cls).filter(cls.sAMAccountName.in_(names)).all()
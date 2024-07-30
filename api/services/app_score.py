from extensions.ext_database import db
from models.model import Message

class AppScore:
    @classmethod
    def getConversationLength(cls,conversation_id: str):
        return db.session.query(Message).filter(Message.conversation_id == conversation_id,Message.status == 'normal' ).count()
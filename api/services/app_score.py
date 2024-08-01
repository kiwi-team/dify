from extensions.ext_database import db
from models.model import Message

class AppScore:
    @classmethod
    def getConversationLength(cls,conversation_id: str):
        return db.session.query(Message).filter(Message.conversation_id == conversation_id,Message.status == 'normal' ).count()

    @classmethod
    def getConversationFirstQuery(cls,conversation_id: str):
        conversation = db.session.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()).first()
        return conversation.query if conversation else ""

    @classmethod
    def getConversationLastAnswer(cls,conversation_id: str):
        conversation = db.session.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.desc()).first()
        return conversation.answer if conversation else ""
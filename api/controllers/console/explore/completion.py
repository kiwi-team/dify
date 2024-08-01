import logging
from datetime import datetime, timezone

from flask_login import current_user
from flask_restful import reqparse
from werkzeug.exceptions import InternalServerError, NotFound
from extensions.ext_redis import redis_client


import services
from controllers.console import api
from controllers.console.app.error import (
    AppUnavailableError,
    CompletionRequestError,
    ConversationCompletedError,
    ProviderModelCurrentlyNotSupportError,
    ProviderNotInitializeError,
    ProviderQuotaExceededError,
)
from controllers.console.explore.error import NotChatAppError, NotCompletionAppError
from controllers.console.explore.wraps import InstalledAppResource
from core.app.apps.base_app_queue_manager import AppQueueManager
from core.app.entities.app_invoke_entities import InvokeFrom
from core.errors.error import ModelCurrentlyNotSupportError, ProviderTokenNotInitError, QuotaExceededError
from core.model_runtime.errors.invoke import InvokeError
from extensions.ext_database import db
from libs import helper
from libs.helper import uuid_value
from models.model import AppMode
from services.app_generate_service import AppGenerateService
from services.app_score import AppScore 
from models.llmtestdb import LLMTestDB


# define completion api for user
class CompletionApi(InstalledAppResource):

    def post(self, installed_app):
        app_model = installed_app.app
        if app_model.mode != 'completion':
            raise NotCompletionAppError()

        parser = reqparse.RequestParser()
        parser.add_argument('inputs', type=dict, required=True, location='json')
        parser.add_argument('query', type=str, location='json', default='')
        parser.add_argument('files', type=list, required=False, location='json')
        parser.add_argument('response_mode', type=str, choices=['blocking', 'streaming'], location='json')
        parser.add_argument('retriever_from', type=str, required=False, default='explore_app', location='json')
        args = parser.parse_args()

        streaming = args['response_mode'] == 'streaming'
        args['auto_generate_name'] = False

        installed_app.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.commit()

        try:
            response = AppGenerateService.generate(
                app_model=app_model,
                user=current_user,
                args=args,
                invoke_from=InvokeFrom.EXPLORE,
                streaming=streaming
            )

            return helper.compact_generate_response(response)
        except services.errors.conversation.ConversationNotExistsError:
            raise NotFound("Conversation Not Exists.")
        except services.errors.conversation.ConversationCompletedError:
            raise ConversationCompletedError()
        except services.errors.app_model_config.AppModelConfigBrokenError:
            logging.exception("App model config broken.")
            raise AppUnavailableError()
        except ProviderTokenNotInitError as ex:
            raise ProviderNotInitializeError(ex.description)
        except QuotaExceededError:
            raise ProviderQuotaExceededError()
        except ModelCurrentlyNotSupportError:
            raise ProviderModelCurrentlyNotSupportError()
        except InvokeError as e:
            raise CompletionRequestError(e.description)
        except ValueError as e:
            raise e
        except Exception as e:
            logging.exception("internal server error.")
            raise InternalServerError()


class CompletionStopApi(InstalledAppResource):
    def post(self, installed_app, task_id):
        app_model = installed_app.app
        if app_model.mode != 'completion':
            raise NotCompletionAppError()

        AppQueueManager.set_stop_flag(task_id, InvokeFrom.EXPLORE, current_user.id)

        return {'result': 'success'}, 200


class ChatApi(InstalledAppResource):
    def post(self, installed_app):
        app_model = installed_app.app
        app_mode = AppMode.value_of(app_model.mode)
        if app_mode not in [AppMode.CHAT, AppMode.AGENT_CHAT, AppMode.ADVANCED_CHAT]:
            raise NotChatAppError()

        parser = reqparse.RequestParser()
        parser.add_argument('inputs', type=dict, required=True, location='json')
        parser.add_argument('query', type=str, required=True, location='json')
        parser.add_argument('files', type=list, required=False, location='json')
        parser.add_argument('conversation_id', type=uuid_value, location='json')
        parser.add_argument('retriever_from', type=str, required=False, default='explore_app', location='json')
        args = parser.parse_args()

        args['auto_generate_name'] = False

        installed_app.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.commit()

        try:
            response = AppGenerateService.generate(
                app_model=app_model,
                user=current_user,
                args=args,
                invoke_from=InvokeFrom.EXPLORE,
                streaming=True
            )

            return helper.compact_generate_response(response)
        except services.errors.conversation.ConversationNotExistsError:
            raise NotFound("Conversation Not Exists.")
        except services.errors.conversation.ConversationCompletedError:
            raise ConversationCompletedError()
        except services.errors.app_model_config.AppModelConfigBrokenError:
            logging.exception("App model config broken.")
            raise AppUnavailableError()
        except ProviderTokenNotInitError as ex:
            raise ProviderNotInitializeError(ex.description)
        except QuotaExceededError:
            raise ProviderQuotaExceededError()
        except ModelCurrentlyNotSupportError:
            raise ProviderModelCurrentlyNotSupportError()
        except InvokeError as e:
            raise CompletionRequestError(e.description)
        except ValueError as e:
            raise e
        except Exception as e:
            logging.exception("internal server error.")
            raise InternalServerError()


class ChatStopApi(InstalledAppResource):
    def post(self, installed_app, task_id):
        app_model = installed_app.app
        app_mode = AppMode.value_of(app_model.mode)
        if app_mode not in [AppMode.CHAT, AppMode.AGENT_CHAT, AppMode.ADVANCED_CHAT]:
            raise NotChatAppError()

        AppQueueManager.set_stop_flag(task_id, InvokeFrom.EXPLORE, current_user.id)

        return {'result': 'success'}, 200


class ChatScoreApi(InstalledAppResource):
    '''
    判断聊天是否获得积分
    code，可以再多一些，0就是获取了积分。1是没有获取，2是达到今日上限, -1是不用弹框
    '''
    def get(self,installed_app, conversation_id):
        app_model = installed_app.app
        app_mode = AppMode.value_of(app_model.mode)
        if app_mode not in [AppMode.CHAT, AppMode.AGENT_CHAT, AppMode.ADVANCED_CHAT]:
            raise NotChatAppError()
        if app_model.pass_type == 'count':
            conversationLength = AppScore.getConversationLength(conversation_id)
            if app_model.pass_config['count'] == conversationLength:
                query = AppScore.getConversationFirstQuery(conversation_id)[:100]
                detail = {
                    "subject":app_model.name+" "+query
                }
                code,score = LLMTestDB.saveReward(current_user.id,0,app_model.score,str(conversation_id),detail)
                return {'code':code,'score':score},200
        elif app_model.pass_type == 'checkpoint':
            fialed_key = "dify:get_score_failed:"+conversation_id
            if redis_client.get(fialed_key):
                return {'score':0,'code':-1},200
            answer = AppScore.getConversationLastAnswer(conversation_id)
            if app_model.pass_config['success_keyword']  and app_model.pass_config['success_keyword'] in answer:
                query = AppScore.getConversationFirstQuery(conversation_id)[:100]
                detail = {
                    "subject":app_model.name+" "+query
                }
                code,score = LLMTestDB.saveReward(current_user.id,0,app_model.score,str(conversation_id),detail)
                return {'code':code,'score':score},200
            if app_model.pass_config['failed_keyword']  and app_model.pass_config['failed_keyword'] in answer:
                # 触发退出机制
                redis_client.set(fialed_key, 1, ex=3600)
                return {'code':1,'score':0},200

        return {'score':0,'code':-1},200


class ChatStartApi(InstalledAppResource):
    def get(self,installed_app):
        app_model = installed_app.app
        app_mode = AppMode.value_of(app_model.mode)
        if app_mode not in [AppMode.CHAT, AppMode.AGENT_CHAT, AppMode.ADVANCED_CHAT]:
            raise NotChatAppError()
        app_model.open_times = app_model.open_times + 1

        #num  = db.session('llmtest').execute('select count(*) from User')
        db.session.commit()
        return {'result': 'success'}, 200
api.add_resource(CompletionApi, '/installed-apps/<uuid:installed_app_id>/completion-messages', endpoint='installed_app_completion')
api.add_resource(CompletionStopApi, '/installed-apps/<uuid:installed_app_id>/completion-messages/<string:task_id>/stop', endpoint='installed_app_stop_completion')
api.add_resource(ChatApi, '/installed-apps/<uuid:installed_app_id>/chat-messages', endpoint='installed_app_chat_completion')
api.add_resource(ChatScoreApi, '/installed-apps/<uuid:installed_app_id>/score/<uuid:conversation_id>')
api.add_resource(ChatStartApi, '/installed-apps/<uuid:installed_app_id>/chat-start')
api.add_resource(ChatStopApi, '/installed-apps/<uuid:installed_app_id>/chat-messages/<string:task_id>/stop', endpoint='installed_app_stop_chat_completion')

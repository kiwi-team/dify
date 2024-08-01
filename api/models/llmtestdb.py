import json

from sqlalchemy import create_engine
from sqlalchemy.sql import text
from configs import dify_config
from libs.date import getUtcNow,getTodayUTCStartAndEnd

engine = create_engine(dify_config.BIND_DB1)
class LLMTestDB:
    @classmethod
    def printUser(cls):
        with engine.connect() as con:
            rs = con.execute(text('SELECT * FROM "User"'))
            for row in rs:
                print(row)

    @classmethod
    def printS2Reward(cls):
        with engine.connect() as con:
            rs = con.execute(text('SELECT * FROM "S2Reward"'))
            for row in rs:
                print(row)
    # 保存积分  
    @classmethod
    def saveReward(cls,userId:str,reward:int, score:int,objectId:str,detail):
        #userId = 'ca8870da-db70-4725-857c-4addfc716cf9'
        data = {
            "userId":userId, 
            "reward": reward, 
            "score": score, 
            "objectId": objectId,
            "remark":"AI乐园获得的奖励",
            "type":1005,
            "updatedAt": getUtcNow(),
            "createdAt": getUtcNow(),
            "detail": json.dumps(detail)
        }
        # 2024-07-11 23:35:41.054
        statement = text("""
        INSERT INTO public."S2Reward" ("userId",reward,score,"objectId",remark,"createdAt","updatedAt","type","detail") VALUES
        (:userId,:reward,:score,:objectId,:remark,:createdAt,:updatedAt,:type,:detail)
        """)
        updateUserStmt = text("""
        UPDATE public."User" SET score = score + :score, 
                            "totalScore" = "totalScore" + :totalScore,
                            "balance" = "balance" + :balance,
                            "totalBalance" = "totalBalance" + :totalBalance 
                            WHERE uid = :uid
                              """)
        checkScoreStmt = text("""
        SELECT sum(score) as total FROM "S2Reward" where "userId" = :userId and type = 1005 and "createdAt" >= :start and "createdAt" <= :end
                              """)
        [start,end]  = getTodayUTCStartAndEnd()
        max = 20
        total = 0
        todayFinish = False
        with engine.connect() as con:
                rs = con.execute(checkScoreStmt,{"userId":userId,"start":start,"end":end})
                for row in rs:
                    total = row[0] if row[0] else 0
                    break
                if total >= max:
                    return [-1,0]
                if total + score >= max:
                    score = max - total
                    data['score'] = score
                    todayFinish = True  # 今日的奖励领取完了
                con.execute(statement, data)
                con.execute(updateUserStmt,{
                    "score": score,
                    "totalScore": score,
                    "balance": reward,
                    "totalBalance": reward,
                    "uid": userId
                })
                con.commit() # 必须要有
        if todayFinish:
            # 0就是获取了积分。1是没有获取，2是达到今日上限
            return [2,score]
        else:
            return [0,score]

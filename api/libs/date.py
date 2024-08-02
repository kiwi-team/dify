from datetime import datetime, timezone,timedelta


def getUtcNow():
    #https://www.w3.org/TR/NOTE-datetime
    # 因为`%f`会输出六位数字代表微秒，而我们只需要前三位表示毫秒。
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]


def getTodayUTCStartAndEnd():
    start = (datetime.now(timezone.utc) + timedelta(hours=8) - timedelta(days=1)).strftime('%Y-%m-%d 16:00:00.000')
    end = (datetime.now(timezone.utc)+timedelta(hours=8)).strftime('%Y-%m-%d 16:00:00.000')
    return [start,end]

def getDateStartEnd(date:str):
    """
    给定一个北京日期，返回它的utc开始和结束时间,还有北京日期
    @param {*} date  string 2024-06-19
	let tmp = DateTime.fromISO(date).plus({days:-1}).toFormat('yyyy-MM-dd');
	let utcDate = [tmp+'T16:00:00.000Z',date+'T16:00:00.000Z',date]; 
    return utcDate;
    """
    pass
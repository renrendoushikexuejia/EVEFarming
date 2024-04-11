# 2023年4月22日12:10:34 准备把这一版本修改为新版

# MoveTo有6个参数,  X Y是移动终点的坐标, XOffset YOffset是终点坐标偏移的最大值,duration是移动所耗费的时间,durationOffset是移动耗费时间的偏移值的最大值。
# MoveRel有6个参数,X Y是移动的相对值,即终点坐标减去起点坐标的差值。XOffset YOffset是差值的偏移最大值,duration是移动所耗费的时间,durationOffset是移动耗费时间的偏移值的最大值。
# FakeTime有3个参数,操作参数1是时间类型 s是秒, m是分钟, h是小时。 操作参数2是最短时间值, 操作参数3是最长时间值
# ClickLeftMulti,ClickRightMulti 有3个参数,操作参数1是点击的次数, 操作参数2是点击的时间间隔 单位是秒s, 操作参数3是时间间隔的偏移值的最大值
# Scroll有2个参数,功能不完善,不建议使用。操作参数1是滚动最小值, 操作参数2是滚动最大值,正数向上滚动,负数向下滚动,只接收一个整数。
# TypeWrite有1个参数,操作参数1 是需要输入的字符串，现在的方法不能输入中文，需要修改。
# KeyDown,KeyUp有1个参数,操作参数1 是需要输入的字符串
# ClickLeft, ClickRight,MouseDown, MouseUp 没有参数
# fMoveCurve有5个参数，X Y是移动终点的坐标, XOffset YOffset是终点坐标偏移的最大值，没有duration。操作参数1是把圆弧简化成多少个线段
# fPress有3个参数，操作参数1是按键名，参数2是按的次数，参数3是两次按键的时间间隔，间隔时间是固定的，没有写随机数。如果需要时间间隔随机，可以用TypeWrite函数，或者按键操作分开写。

import random, math, time
import pyautogui as pag
# 定义全局常量
pag.FAILSAFE = True
SAFETIME = 0.5        # 用于time.sleep( SAFETIME)   在每次键鼠操作之后停止时间,确保操作完成
MOVETYPELIST = [pag.easeInQuad,pag.easeOutQuad,pag.easeInOutQuad,pag.easeInCubic,pag.easeOutCubic,pag.easeInOutCubic,
        pag.easeInQuart,pag.easeOutQuart,pag.easeInOutQuart,pag.easeInQuint,pag.easeOutQuint,pag.easeInOutQuint,pag.easeInSine,
        pag.easeOutSine,pag.easeInOutSine,pag.easeInExpo,pag.easeOutExpo,pag.easeInOutExpo,pag.easeInCirc,pag.easeOutCirc,pag.easeInOutCirc,
        pag.easeInElastic,pag.easeOutElastic,pag.easeInOutElastic,pag.easeInBack,pag.easeOutBack,pag.easeInOutBack,pag.easeInBounce,
        pag.easeOutBounce,pag.easeInOutBounce]      # 鼠标移动函数的移动方式列表

# 定义键鼠操作, 函数是从keyGhost复制过来的,不是每个都用上了

def fMoveCurve( X, Y, XOffset, YOffset, cutCount):      # 代码是抄ChatGPT的   cutCount是指把圆弧分成几段,分段越多，鼠标移动越慢，圆弧越平滑
    maxX, maxY = pag.size()     # 求屏幕最大尺寸
    startX, startY = pag.position()     # 从鼠标当前位置开始移动
    endX = random.randint( X - XOffset, X + XOffset)    # 结束点由参数取得
    endY = random.randint( Y - YOffset, Y + YOffset)
    randomX = random.randint( 0, maxX)      # 屏幕坐标内随机一个点，用来和起点 终点 一起确定一个圆形
    randomY = random.randint( 0, maxY)      # 这个随机点的坐标取值范围要调整，否则会出现起笔是竖线的情况------------
    # 计算圆心的位置
    k1 = (endX - startX) / (startY - endY)
    b1 = (startX**2 - endX**2 + startY**2 - endY**2) / 2 / (startY - endY)
    k2 = (randomX - endX) / (endY - randomY)
    b2 = (endX**2 - randomX**2 + endY**2 - randomY**2) / 2 / (endY - randomY)
    x = (b2 - b1) / (k1 - k2)
    y = k1 * x + b1
    centerX = round(x)  # 圆心centerX, centerY
    centerY = round(y)

    # 计算圆的半径
    radius = math.sqrt((startX - centerX)**2 + (startY - centerY)**2)
    radius = round( radius)

    # 在函数中定义一个函数， 已知圆心坐标centerX, centerY, 半径radius, 圆上任意一点的X坐标，求对应X的Y坐标
    def get_y_coordinate(centerX, centerY, radius, x):
        y = math.sqrt(radius**2 - (x - centerX)**2) + centerY
        return y

    # # 计算圆上的任意一点的位置
    # step = 0.01
    # results = []
    # for x in range(int(center[0] - radius), int(center[0] + radius)):
    #     theta = math.acos((x - center[0]) / radius)
    #     y = get_y_coordinate(center, radius, x)
    #     results.append((x, y))
    # # 返回X和Y之间圆弧上所有点的坐标
    # # return results

    results = []    # 根据X值求得圆弧上的点，加入列表results
    if startX <= endX:
        for x in range( startX, endX, 1):
            y = get_y_coordinate( centerX, centerY, radius, x)
            y = round(y)
            results.append((x, y))
            # 在实际应用中，从起点突然画出一条很长的线段，然后才开始画曲线，是因为圆上有一部分的X值比起点的X值小，
            # 而这里只取了比起点X值大的一部分圆弧。解决这个问题只需要限制随机点的取值范围 randomX, randomY
            # 同理，当startX > endX时 会出现一部分圆弧缺失的情况。
    elif startX > endX:
        for x in range( startX, endX, -1):
            y = get_y_coordinate( centerX, centerY, radius, x)
            y = round(y)
            results.append((x, y))
    
    # 每个点都MoveTo 速度太慢了。新建一个列表，选出一部分点来MoveTo
    # 这里len(results)-1， results[i+1]是去掉坐标列表中的第一个点和最后一个点，在不修改randomX,randomY取值范围
    # 的情况下解决起笔画直线的问题
    pickResults = []
    for i in range( 0, len(results)-1, round( len(results) / cutCount)):
        pickResults.append( results[i+1])
    #先把鼠标移动到弧线的起始点，避免起笔画竖线速度太快被检测。 但是还没有解决起笔竖线的问题。解决根本问题还得改randomX,randomY的取值
    pag.moveTo( pickResults[0][0], pickResults[0][1], duration=0.2)     
    for x, y in pickResults:
        pag.moveTo( x, y)
    return startX, startY, endX, endY, centerX, centerY, radius, cutCount

def fMoveTo( X, Y, XOffset, YOffset, duration, durationOffset):
    X = random.randint( X - XOffset, X + XOffset)
    Y = random.randint( Y - YOffset, Y + YOffset)
    duration = random.uniform( duration - durationOffset, duration + durationOffset)       #duration为移动到目标点的指定耗时
    moveType = random.choice( MOVETYPELIST)      #定义鼠标的移动方式           
    pag.moveTo( X, Y, duration=duration, tween=moveType)
    #返回值,实际移动到的坐标X,Y,实际耗时duration,移动方式moveType
    duration = round( duration, 2)
    return X, Y, duration, moveType

def fMoveRel( X, Y, XOffset, YOffset, duration, durationOffset):
    X = random.randint( X - XOffset, X + XOffset)
    Y = random.randint( Y - YOffset, Y + YOffset)
    duration = random.uniform( duration - durationOffset, duration + durationOffset)       #duration为移动到目标点的指定耗时
    moveType = random.choice( MOVETYPELIST)      #定义鼠标的移动方式           
    pag.moveRel( X, Y, duration=duration, tween=moveType)
    #返回值,实际移动到的坐标X,Y,实际耗时duration,移动方式moveType
    duration = round( duration, 2)
    return X, Y, duration, moveType    

def fClickLeft():
    pag.click( button='left')

def fClickRight():
    pag.click( button='right')

def fClickLeftMulti( clicks, interval, intervalOffset=0.15):      # 参数clicks是点击次数, interval是两次点击的时间间隔, intervalOffset是点击的时间间隔的偏移值,使每两次点击的时间间隔不一样
    for i in range( 0, clicks):
        pag.click( button='left')
        fFakeTime( 's', interval - intervalOffset, interval + intervalOffset)

def fClickRightMulti( clicks, interval, intervalOffset=0.15):     # 参数clicks是点击次数, interval是两次点击的时间间隔, intervalOffset是点击的时间间隔的偏移值,使每两次点击的时间间隔不一样
    for i in range( 0, clicks):
        pag.click( button='right')
        fFakeTime( 's', interval - intervalOffset, interval + intervalOffset)

def fScroll( min, max):     # 参数1是最小值,参数2是最大值  pyautogui的滚动一次到位,要改成循环步进
    if min > max:
        pag.alert(text='Scroll 参数1 > 参数2', title='错误')
        return 0
    fakeScrollNum = random.randint( min, max)
    fakeCountAbs = abs(fakeScrollNum // 30)
    if fakeScrollNum >= 0:
        for i in range( 0, fakeCountAbs):
            pag.scroll(80)
            fFakeTime( 's', 0.1, 0.3)
    else:
        for i in range( 0, fakeCountAbs):
            pag.scroll( -80)
            fFakeTime( 's', 0.1, 0.3)
    return fakeScrollNum

def fMouseDown():
    pag.mouseDown()

def fMouseUp():
    pag.mouseUp()

def fTypeWrite( strParam):      #这个方法不能输入中文
    for i in strParam:
        pag.keyDown( i)
        # fFakeTime( 's', 0.05, 0.1)
        pag.keyUp( i)
        fFakeTime( 's', 0.1, 0.5)
    return strParam

def fKeyDown( strParam):
    pag.keyDown( strParam)
    return strParam

def fKeyUp( strParam):
    pag.keyUp( strParam)
    return strParam

def fPress( charParam, presses, interval):  # charParam是按下并弹起的按键， presses是按键次数， interval是两次按键的时间间隔
    pag.press( charParam, presses=presses, interval=interval)

# 定义时间操作
# timeType是时间类型字符串,s是秒,m是分,h是小时。min是最短的s/m/h。 max是最大的s/m/h
def fFakeTime(timeType, min=1.0, max=10.0):  
    fakeTimeNum = random.uniform( min, max)
    if timeType == 's':
        time.sleep( fakeTimeNum)
    elif timeType == 'm':
        time.sleep( fakeTimeNum*60)
    elif timeType == 'h':
        time.sleep( fakeTimeNum*3600)
    else:
        # 窗口显示必须主线程中去管理不能在子线程中去调用显示,否则就会导致页面卡死。
        # QMessageBox.information( None, '提示', 'FakeTime操作参数1  时间单位应该是秒s,分m,小时h')  会卡死
        pag.alert( title='错误', text='FakeTime操作参数1  时间单位应该是秒s,分m,小时h')
    fakeTimeNum = round( fakeTimeNum, 2)
    return fakeTimeNum

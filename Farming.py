import threading,os,json,datetime,time,random,io,requests
import win32gui 
from PyQt5.QtWidgets import QMainWindow,QApplication,QMessageBox,QTableWidgetItem,QInputDialog
from PyQt5.QtCore import pyqtSignal, QBuffer, QIODevice, QUrl
from PyQt5 import QtMultimedia
import MyFake as fk
import pyautogui as pag
from Ui_Farming import Ui_Farming
from Bind import Bind
from PIL import Image       # 引入Image模块,注意使用时不要重名
from cnocr import CnOcr
from system_hotkey import SystemHotkey
import warnings

warnings.filterwarnings("ignore", category=UserWarning)     # 为了忽略cnocr中的一个警告

# 定义全局变量
ISRUN = False
gDuration = 0.8
gDurationOffset = 0.3

# 定义函数
# 传入一个PIL的Image对象, 返回值为识别出来的所有汉字的一个字符串
def fOcr(PILImage):
    ocr = CnOcr()
    res = ocr.ocr(PILImage)
    str = ''
    for line in res:
        str += line['text']
    return str

# 把QImage对象转换为PIL的Image对象
def qimage_to_pil_image(qimage):
    buffer = QBuffer()
    buffer.open(QIODevice.ReadWrite)
    qimage.save(buffer, "PNG")
    return Image.open(io.BytesIO(buffer.data()))

# 判断截图的指定矩形范围内有没有指定RGB范围内的颜色
def fCheckImage(img, top_left_x, top_left_y, bottom_right_x, bottom_right_y, r_min, r_max, g_min, g_max, b_min, b_max):
    for x in range(top_left_x, bottom_right_x + 1):
        for y in range(top_left_y, bottom_right_y + 1):
            color = img.pixelColor(x, y)
            r, g, b, _ = color.getRgb()
            if r_min <= r <= r_max and g_min <= g <= g_max and b_min <= b <= b_max:
                # print('x,y,r,g,b', x,y,r,g,b)       # 调试用
                return True
    return False

# 对游戏窗口截图,并以当前时间和窗口名为文件名保存,用于调试
def fScreenShot(hwnd):
    img = QApplication.primaryScreen().grabWindow( int(hwnd)).toImage()     #hwnd是正整数，传的参数是字符串
    if img.isNull():        
        QMessageBox.information(None, "提示", "请保持游戏窗口显示,不要最小化")
        return False
    saveName = 'shot/shot' + datetime.datetime.now().strftime('%H%M%S') + '.png'    # shot/ 是指保存在shot文件夹下
    if not os.path.exists('shot'):
        os.makedirs('shot')
    img.save(saveName)
    # print('screen shot save over')      

# 对游戏窗口进行截图,判断游戏状态
def fCheckState(hwnd):
    state = {}      # 创建字典用来保存状态信息
    img = QApplication.primaryScreen().grabWindow( int(hwnd)).toImage()     #hwnd是正整数，传的参数是字符串
    if img.isNull():    # 这里有问题, 截图失败会显示一个黑色的窗口, 不一定是Null
        QMessageBox.information(None, "提示", "请保持游戏窗口显示,不要最小化")
        return False
    img.save('checkState.png')      # 测试完成后把这一行注释掉

    # 是否会战模式, 随便截图一块区域,只要有颜色,就不是会战模式  这里截的是窗口正下方的一块区域
    if fCheckImage(img, 730, 876, 836, 946, 20, 255, 20, 255, 20, 255):  
        state['battleMode'] = False
    else:
        state['battleMode'] = True

    # 是否在空间站内 判断离站按钮右下角的蓝色(82, 162, 189)(90,166,189)
    if fCheckImage(img, 1254, 299, 1273, 315, 67, 97, 147, 177, 174, 204):
        state['station'] = True
    else:
        state['station'] = False

    # 判断本地玩家列表中的 糟糕/不良/中立 图标,不是判断图标中横杠, 而是图标颜色
    # 区域位置(166,160)--(169,586)   红-颜色(149,6,6)(148,4,0)  白=颜色(140,140,140)(140,142,140)
    # 这里分为4个判断,因为要判断灰色和红色两种颜色. 并且判断区域要隔过星币余额提示框. 星币提示框刚好和第7/8个玩家列表重合,所有无法检测7/8玩家是白名还是红名
    if fCheckImage(img, 166, 160, 169, 271, 134, 163, -1, 15, -1, 15) \
        or fCheckImage(img, 166, 299, 169, 586, 134, 163, -1, 15, -1, 15)\
        or fCheckImage(img, 166, 160, 169, 271, 125, 155, 125, 155, 125, 155) \
        or fCheckImage(img, 166, 299, 169, 586, 125, 155, 125, 155, 125, 155):
        state['danger'] = True
        fScreenShot(hwnd)       # 调试用,  在有危险的时候截图保存.
    else:
        state['danger'] = False

    # 判断是否有野怪  野怪红色(214,24,24)  判断区域(1002,263)--(1023,568)
    if fCheckImage(img, 1002, 263, 1023, 568, 199, 230, 9, 39, 9, 39):
        state['creep'] = True
    else:
        state['creep'] = False
    
    # 判断野怪距离是否太远(1036,264)(1038,568)  判断的是数字'1'最顶上左边的尖
    if fCheckImage(img, 1036, 264, 1038, 568, 200, 256, 200, 256, 200, 256):
        state['creepTooFar'] = True
    else:
        state['creepTooFar'] = False


    # 判断屏幕中下方是否出现 跃迁引擎启动,正在跳跃,正在建立跃迁航向,接近中,正在朝向
    # 判断纯白色(255,255,255)字体   不能用灰色(156,154,156)字体, 因为残骸和灰色字体颜色一样
    # 这个地方特别注意, '环绕中'三个字会被检测成跃迁状态,导致误判, 操作流程上出现错误, 跃迁状态下会跳过后面所有的操作.
    # 判断时避开'环绕中'三个字, 取后面位置的字.
    if fCheckImage(img, 653, 664, 684, 689, 230, 256, 230, 256, 230, 256):   
        state['jump'] = True
    else:
        state['jump'] = False

    # 判断无人机是否在攻击
    if fCheckImage(img, 387, 191, 458, 283, 230, 256, 50, 85, 59, 90):      # 红色(239,65,66)(247,65,74)(255,69,74)
        state['UAVattack'] = True
    else:
        state['UAVattack'] = False

    # 判断无人机是否在返回状态
    if fCheckImage(img, 387, 191, 458, 283, 235, 256, 170, 201, 50, 80):        # 黄色(255,186,66)(247,174,66)
        state['UAVreturn'] = True
    else:
        state['UAVreturn'] = False

    # 判断无人机是否空闲
    if fCheckImage(img, 387, 191, 458, 283, 125, 155, 180, 210, 85, 122):      #  绿色(140,195,107)(132,186,99)
        state['UAVidle'] = True
    else:
        state['UAVidle'] = False

    # 判断无人机是未释放状态
    if state['UAVattack'] == False and state['UAVreturn'] == False and state['UAVidle'] == False:
        state['UAVground'] = True
    else:
        state['UAVground'] = False

    # 护盾或装甲损坏  护盾或装甲50%多一点位置显示红色(148,16,16)(156,16,16),  要回空间站修船  
    if fCheckImage(img, 546, 788, 643, 862, 120, 170, 1, 35, 1, 35):
        state['damaged'] = True
    else:
        state['damaged'] = False


    # 船炸了  出现星捷运复原服务黄色字体(222,142,0)
    if fCheckImage(img, 740, 166, 815, 189, 202, 237, 128, 157, -1, 16):
        state['destroyed'] = True
    else:
        state['destroyed'] = False

    # 掉线了  判断连接丢失窗口的退出按钮的右下角蓝色(90,166,189)(82,162,189)
    if fCheckImage(img, 807, 551, 858, 620, 70, 100, 148, 182, 170, 205):
        state['disconnected'] = True
    else:
        state['disconnected'] = False


    # print(state)
    return state


def fCheckCreeper(hwnd):
    img = QApplication.primaryScreen().grabWindow( int(hwnd)).toImage()     #hwnd是正整数，传的参数是字符串
    if img.isNull():
        QMessageBox.information(None, "提示", "请保持游戏窗口显示,不要最小化")
        return False
    # img.save('checkCreep.png')      # 测试完成后把这一行注释掉
    pilImage = qimage_to_pil_image(img)     # 把QImage对象转换为PIL的Image对象
    cropped_image = pilImage.crop((1075, 261, 1250, 570))      # 截取图片, 总览--刷怪--名字一栏
    cropped_image.save('checkCreep.png')        # 测试完成后把这一行注释掉
    # cropped_image.show()
    ocrStr = fOcr(cropped_image)
    # print('识别出的文字--',ocrStr)
    # 官员, 旗舰, boss, 矿船 名字的集合     还加了一些容易识别错的字,比如 '舰'识别为'成'
    # 这里本来写的是区别判断每一种类型的野怪, 后来改成所有特殊的野怪一起判断出来,不再区分
    # guanyuanSet = set('尔科3比戈安杰密利卓拉威恩切克P罗马雅察6W捷托卡赞迈图纳5泰朵勒尼塞里鲁万布姆瑟达加奥斯哈索蓓瑞丹F隆莱塔弗梅瓦埃赛兰4阿帕D博佐林兹米门玛德特')
    # qijianSet = set('被占据的航空母舰成')
    # xiaobossSet = set('缚魂')
    # kuangchuanSet = set('自由护航主体运载拖拉')
    ocrSet = set(ocrStr)
    # 无人机区官员名称: D-34343单元  F-435454单元  P-343554单元  W-634单元
    specialCreeperSet = set('尔科3比戈安杰密卓威恩克P罗雅察6W捷托卡赞迈图纳5泰朵勒尼塞里鲁万布瑟达奥哈索蓓瑞丹F隆\
                    莱塔弗梅埃赛兰4帕D博佐兹米门玛德单元')    
    # 没有'载', 运载舰和核搭载无人机都有'载'字,  2023年5月18日 specialCreeperSet 去掉'成缚魂'  '成'不知道是哪个字检测错了
    # 2023年5月21日 specialCreeperSet去掉'林''特''马',不知道是哪个字识别成了'林''特''马'
    # 2023年5月25日 specialCreeperSet去掉'阿', '瓦', '斯', '姆' 因为无人机区官员没这四个字,并且和boss名称重复
    bargeCreeperSet = set('自由护体运输拖拉')
    skippedCreeperSet = set('被占据的超航空母舰')     # '缚魂占据的超级' 也是要跳过的.  去掉'级' 因为普通野怪有'高级'
    bossCreeperSet = set('缚魂阿瓦姆钟斯')        # '缚'会被检测为'钟'. 去掉'者' 因为有'无人机控制者'. 去掉'肇事', 普通野怪也有'肇事'

    bargeSet = ocrSet & bargeCreeperSet
    specialSet = ocrSet & specialCreeperSet
    skippedSet = ocrSet & skippedCreeperSet
    bossSet = ocrSet & bossCreeperSet
    returnSet = set()       # 作为返回值的空集合, 返回空集合或者被检测到的字符

    # 这里的顺序很重要
    if ocrSet:
        creeperType = 'common'   # 'common' 是指普通的野怪
        returnSet = ocrSet

    # boss在前 skipped在后 是为了跳过'缚魂的航空母舰'
    if bossSet:
        creeperType = 'boss'
        returnSet = bossSet

    if skippedSet:
        creeperType = 'skipped'
        returnSet = skippedSet

    if bargeSet:
        creeperType = 'barge'
        returnSet = bargeSet

    if specialSet:
        creeperType = 'special'
        returnSet = specialSet

    # print('特殊野怪', specialSet, bossSet, bargeSet)
    # print('略过的野怪', skippedSet)
    # print('creepType--',creeperType)
    return creeperType, returnSet      # 返回野怪类型(common, special, boss, skipped, barge) 和 检测到的字符的集合  还有函数执行错误时返回的False



# 游戏操作函数
# 返回空间站
def gameGoHome():
    # 返回空间站的点,要命名为HOME或者任意四个英文字符,以保证位置正确
    # 移动到星系名前面的小太阳 --这个位置不固定,导致了整个菜单的位置错误, 这也就是为什么一直调菜单,一直出错.但是不影响使用
    # 这里每一次移动位置之后都要左键点一下,是为了防止移动时经过其他菜单 有自动打开的其他菜单.
    # 回家之前先用键盘收回一次无人机, 不调用gameRetrieveUAV()是因为gameGoHome()不需要等待时间,有时候需要尽快返回
    fk.fKeyDown('shift')
    fk.fFakeTime('s', 0.2, 0.5)
    fk.fKeyDown('r')
    fk.fFakeTime('s', 0.2, 0.5)
    fk.fKeyUp('r')
    fk.fKeyUp('shift')
    fk.fFakeTime('s', 0.2, 0.5)

    fk.fMoveTo(82, 116, 3, 3, gDuration, gDurationOffset)      
    fk.fFakeTime('s', 0.5, 0.7)
    fk.fClickLeft()
    fk.fFakeTime('s', 0.5, 0.7)
    fk.fMoveTo(160, 286, 4, 4, gDuration, gDurationOffset)        # 移动到地点选项
    fk.fFakeTime('s', 0.5, 0.7)
    fk.fClickLeft()
    fk.fFakeTime('s', 0.5, 0.7)
    # fk.fMoveTo(281, 333, 4, 4, gDuration, gDurationOffset)        # 移动到保存的点
    pag.moveTo(281, 333, 0.5)       # 这里使用pyautogui, 使鼠标直接移动到指定位置
    # fk.fFakeTime('s', 0.5, 0.7)
    # fk.fClickLeft()
    fk.fFakeTime('s', 0.5, 0.7)
    fk.fMoveRel(107, 1, 0, 0, gDuration, gDurationOffset)        # 点击停靠
    fk.fFakeTime('s', 0.5, 0.7)
    fk.fClickLeft()
    fk.fFakeTime('s', 0.5, 0.7)

    # 回空间站操作时,在进站之后,出现'离站'按钮之前,会被判断为在太空中无危险状态,然后进行跃迁操作,点击小行星信息,遮挡界面
    # 这个问题需要解决. 在多窗口情况下, 出问题的可能很小.单窗口并且电脑卡的情况下肯定出问题
    # 这个问题已经解决了,每次出站前点击小行星信息页面关闭按钮的位置,不管有没有页面都点一下

# 锁定目标
def gameLockTarget():
    fk.fFakeTime('s', 0.4, 0.7)
    fk.fKeyDown('ctrl')
    fk.fFakeTime('s', 0.2, 0.5)
    fk.fKeyDown('q')
    fk.fFakeTime('s', 0.2, 0.5)
    fk.fKeyUp('q')
    fk.fKeyUp('ctrl')
    
# 释放无人机
def gameReleaseUAV():
    # actionType = random.choice(['k', 'm'])
    actionType = 'k'        # 这里有键盘k 鼠标m 两种方式   这里只用键盘方式,防止鼠标点错
    if actionType == 'k':
        fk.fKeyDown('shift')
        fk.fFakeTime('s', 0.2, 0.5)
        fk.fKeyDown('f')
        fk.fFakeTime('s', 0.2, 0.5)
        fk.fKeyUp('f')
        fk.fFakeTime('s', 0.2, 0.5)
        fk.fKeyUp('shift')
        fk.fFakeTime('s', 0.2, 0.5)
    elif actionType == 'm':
        fk.fMoveTo(407, 174, 66, 7, gDuration, gDurationOffset) 
        fk.fFakeTime('s', 0.4, 0.7)
        fk.fClickRight()
        fk.fFakeTime('s', 0.4, 0.7)
        fk.fMoveRel(60, 15, 10, 4, gDuration, gDurationOffset)
        fk.fFakeTime('s', 0.4, 0.7)
        fk.fClickLeft()
        fk.fFakeTime('s', 0.4, 0.7)

# 环绕目标
def gameCirclingTarget():
    # actionType = random.choice(['k', 'm'])
    actionType = 'k'        # 这里有键盘k 鼠标m 两种方式   这里只用键盘方式,防止鼠标点错
    if actionType == 'k':
        fk.fKeyDown('w')
        fk.fFakeTime('s', 0.2, 0.5)
        fk.fKeyUp('w')
        fk.fFakeTime('s', 0.2, 0.5)
    elif actionType == 'm':
        fk.fMoveTo(831, 132, 5, 5, gDuration, gDurationOffset)      # 移动到环绕按钮
        fk.fFakeTime('s', 0.2, 0.5)
        fk.fClickLeft()
        fk.fFakeTime('s', 0.2, 0.5)

# 选择总览中第一个野怪
def gameSelectFirstCreeper():
    fk.fMoveTo(1156, 306, 50, 3, gDuration, gDurationOffset)
    fk.fFakeTime('s', 0.4, 0.7)
    fk.fClickLeft()
    fk.fFakeTime('s', 0.4, 0.7)

# 点击总览中的刷怪一栏
def gameClickShuaGuai():
    fk.fMoveTo(1085, 247, 3, 3, gDuration, gDurationOffset)     # 移动到总览--刷怪
    fk.fFakeTime('s', 0.2, 0.5)
    fk.fClickLeft()
    fk.fFakeTime('s', 0.2, 0.5)

# 打开护盾
def gameActivateShield():
    # actionType = random.choice(['k', 'm'])      # 键盘k或者鼠标m操作
    actionType = 'k'        # 这里有键盘k 鼠标m 两种方式   这里只用键盘方式,防止鼠标点错
    if actionType == 'k':
        fk.fKeyDown('alt')
        fk.fKeyDown('f1')
        fk.fFakeTime('s', 0.2, 0.5)
        fk.fKeyUp('f1')
        fk.fKeyUp('alt')
        fk.fFakeTime('s', 0.2, 0.5)

        fk.fKeyDown('alt')
        fk.fKeyDown('f2')
        fk.fFakeTime('s', 0.2, 0.5)
        fk.fKeyUp('f2')
        fk.fKeyUp('alt')
        fk.fFakeTime('s', 0.2, 0.5)
        
    elif actionType == 'm':
        fk.fMoveTo(631, 697, 13, 10, gDuration, gDurationOffset)     # 点击左边护盾
        fk.fFakeTime('s', 0.2, 0.5)
        fk.fClickLeft()
        fk.fFakeTime('s', 0.2, 0.5)
        fk.fMoveTo(681, 697, 13, 10, gDuration, gDurationOffset)     # 点击右边护盾  
        fk.fFakeTime('s', 0.2, 0.5)
        fk.fClickLeft()
        fk.fFakeTime('s', 0.2, 0.5)

# 打开会战模式
def gameActivateBattleMode():
    fk.fKeyDown('ctrl')
    fk.fFakeTime('s', 0.2, 0.5)
    fk.fKeyDown('shift')
    fk.fFakeTime('s', 0.2, 0.5)
    fk.fKeyDown('f9')
    fk.fFakeTime('s', 0.2, 0.5)
    fk.fKeyUp('f9')
    fk.fKeyUp('shift')
    fk.fKeyUp('ctrl')
    fk.fFakeTime('s', 0.2, 0.5)

# 出站
def gameLeaveStation():
    fk.fMoveTo(1143, 322, 50, 10, gDuration, gDurationOffset)        # 鼠标移动到出站按钮 
    fk.fFakeTime('s', 0.2, 0.5)       
    fk.fClickLeft()     # 点击出站按钮   
    fk.fFakeTime('s', 11, 12)       # 等待出站完成

# 回收无人机
def gameRetrieveUAV():
    # actionType = random.choice(['k', 'm'])
    actionType = 'k'        # 这里有键盘k 鼠标m 两种方式   这里只用键盘方式,防止鼠标点错
    if actionType == 'k':
        fk.fKeyDown('shift')
        fk.fFakeTime('s', 0.2, 0.5)
        fk.fKeyDown('r')
        fk.fFakeTime('s', 0.2, 0.5)
        fk.fKeyUp('r')
        fk.fFakeTime('s', 0.2, 0.5)
        fk.fKeyUp('shift')
        fk.fFakeTime('s', 0.2, 0.5)
    elif actionType == 'm':
        fk.fMoveTo(416, 199, 75, 7, gDuration, gDurationOffset)
        fk.fFakeTime('s', 0.4, 0.7)
        fk.fClickRight()
        fk.fFakeTime('s', 0.4, 0.7)
        fk.fMoveRel(60, 64, 10, 3, gDuration, gDurationOffset)
        fk.fFakeTime('s', 0.4, 0.7)
        fk.fClickLeft()
        fk.fFakeTime('s', 0.4, 0.7)
    fk.fFakeTime('s', 1, 2)        # 等待无人机返航----我感觉这个等待可以去掉. 尤其是多窗口时,点完回收无人机,直接切换到下一个窗口

# 在空间站内维修飞船
def gameRepairShip():
    fk.fMoveTo(745, 260, 2, 2, gDuration, gDurationOffset)        # 鼠标移动到指定位置,点击有可能存在的小行星带信息页面
    fk.fFakeTime('s', 0.2, 0.5)
    fk.fClickLeft()     # 点击关闭按钮x
    fk.fFakeTime('s', 0.2, 0.5)
    # 点击右侧螺丝刀按钮修船暂时不能用  等游戏更新
    # fk.fMoveTo(979, 193, 5, 5, gDuration, gDurationOffset)        # 移动到界面右侧 扳手螺丝刀维修标志
    # fk.fFakeTime('s', 0.4, 0.7)
    # fk.fClickLeft()
    # fk.fFakeTime('s', 0.5, 0.7)         
    # fk.fMoveTo(523, 378, 168, 10, gDuration, gDurationOffset)      # 移动到中间弹出的维修界面, 选择第一个飞船. 这里一定要把当前使用的飞船放在第一个位置.
    # fk.fFakeTime('s', 0.5, 0.7)
    # fk.fClickLeft()
    # fk.fFakeTime('s', 0.5, 0.7)
    # fk.fMoveTo(519, 556, 30, 7, gDuration, gDurationOffset)         # 移动到下方的修理物品按钮
    # fk.fFakeTime('s', 0.5, 0.7)
    # fk.fClickLeft()
    # fk.fFakeTime('s', 0.5, 0.7)
    # fk.fMoveTo(560, 556, 30, 7, gDuration, gDurationOffset)        # 移动到全部修理按钮
    # fk.fFakeTime('s', 0.5, 0.7)
    # fk.fClickLeft()
    # fk.fFakeTime('s', 0.5, 0.7)
    # fk.fMoveTo(960, 339, 13, 12, gDuration, gDurationOffset)        # 移动到界面右侧 扳手螺丝刀维修标志
    # fk.fFakeTime('s', 0.5, 0.7)
    # fk.fClickLeft()
    # fk.fFakeTime('s', 0.5, 0.7) 

    # 下面是点击仓库 选择舰船 获取维修报价 修船  现在有bug获取维修报价需要点两次才会弹出窗口
    # fk.fMoveTo(23, 367, 3, 3, gDuration, gDurationOffset)        # 移动到界面左侧, 点击仓库
    # fk.fFakeTime('s', 0.4, 0.7)
    # fk.fClickLeft()
    # fk.fFakeTime('s', 0.5, 0.7)         

    # 2023年5月29日暂停舰船维修功能
    # fk.fMoveTo(654, 86, 20, 4, gDuration, gDurationOffset)      # 移动到仓库中的当前舰船标签
    # fk.fFakeTime('s', 0.5, 0.7)
    # fk.fClickRight()
    # fk.fFakeTime('s', 0.5, 0.7)
    # fk.fMoveRel(120, 88, 10, 4, gDuration, gDurationOffset)         # 移动到右键菜单,获取维修报价
    # fk.fFakeTime('s', 0.5, 0.7)
    # fk.fClickLeft()
    # fk.fFakeTime('s', 0.5, 0.7)
    # fk.fMoveTo(654, 86, 20, 4, gDuration, gDurationOffset)      # 移动到仓库中的当前舰船标签
    # fk.fFakeTime('s', 0.5, 0.7)
    # fk.fClickRight()
    # fk.fFakeTime('s', 0.5, 0.7)
    # fk.fMoveRel(120, 88, 10, 4, gDuration, gDurationOffset)         # 移动到右键菜单,获取维修报价
    # fk.fFakeTime('s', 0.5, 0.7)
    # fk.fClickLeft()
    # fk.fFakeTime('s', 0.5, 0.7)
    # fk.fMoveTo(648, 602, 10, 4, gDuration, gDurationOffset)        # 移动到全部修理按钮
    # fk.fFakeTime('s', 0.5, 0.7)
    # fk.fClickLeft()
    # fk.fFakeTime('s', 0.5, 0.7)
    # fk.fMoveTo(780, 340, 2, 2, gDuration, gDurationOffset)        # 移动到维修窗口右上角 点击x
    # fk.fFakeTime('s', 0.5, 0.7)
    # fk.fClickLeft()
    # fk.fFakeTime('s', 0.5, 0.7) 

    # fk.fMoveTo(23, 367, 3, 3, gDuration, gDurationOffset)        # 移动到界面左侧, 点击仓库, 关闭仓库
    # fk.fFakeTime('s', 0.4, 0.7)
    # fk.fClickLeft()
    # fk.fFakeTime('s', 0.5, 0.7)

# 跃迁到第n个星带
def gameJumpTo(n):
    # 移动到星系名前面的小太阳 --这个位置不固定,导致了整个菜单的位置错误, 这也就是为什么一直调菜单,一直出错.但是不影响使用
    fk.fMoveTo(82, 116, 3, 3, gDuration, gDurationOffset)       # 移动到星系名前面的小太阳
    fk.fFakeTime('s', 0.4, 0.7)
    fk.fClickLeft()
    fk.fFakeTime('s', 0.4, 0.7)
    fk.fMoveTo(163, 171, 5, 4, gDuration, gDurationOffset)     # 移动到小行星带选项
    fk.fFakeTime('s', 0.4, 0.7)
    fk.fMoveRel(141, 0, 0, 0, gDuration, gDurationOffset)       # 移动到小行星带列表
    fk.fFakeTime('s', 0.4, 0.7)

    fk.fMoveTo(291, 172+(n-1)*21, 15, 3, gDuration, gDurationOffset)   # 第一个星带中间位置是(291,172)     
    fk.fFakeTime('s', 0.4, 0.7)
    fk.fClickLeft()         
    # 这个地方要左键点一下,如果当前位置没有星带菜单,可以使前面出现的其他星带的菜单消失
    # fk.fMoveRel(155, 1, 0, 0, gDuration, gDurationOffset)       # 鼠标向右移动,点击跃迁至XXX米
    # fk.fFakeTime('s', 0.4, 0.7)

    # 23个星带之前,鼠标直接右移可以点击跃迁至XXX米, 23及以后 需要移动鼠标到固定位置才能跃迁
    # if n > 22:
    #     fk.fMoveTo(509, 608, 60, 6, gDuration, gDurationOffset)
    #     fk.fFakeTime('s', 0.5, 0.8)

    # fk.fClickLeft()

# 出站后,先选择一个星带起跳,然后停止舰船,这样的话跃迁提示会变成纯白色(255,255,255),否则是灰色(156,154,156)
def gameJumpStop():
    gameJumpTo(8)   # 跳到第8个星带,这个位置很重要. 如何星带菜单没有点出来,这个点击位置选择一定要避过无人机挂舱的菜单.

    fk.fFakeTime('s', 1.5, 2)     # 等待起跳
    fk.fMoveTo(582, 924, 5, 3, gDuration, gDurationOffset)      # 移动到屏幕下方的减号位置,点击停止舰船
    fk.fFakeTime('s', 0.4, 0.7)
    fk.fClickLeft()
    fk.fFakeTime('s', 0.4, 0.7)

# 与失踪的无人机取得联系  快捷键要自己设置, Shift + ]
def gameContactUAV():
    fk.fFakeTime('s', 0.2, 0.5)
    fk.fKeyDown('shift')
    fk.fFakeTime('s', 0.2, 0.5)
    fk.fKeyDown(']')
    fk.fFakeTime('s', 0.2, 0.5)
    fk.fKeyUp(']')
    fk.fKeyUp('shift')
    fk.fFakeTime('s', 0.2, 0.5)

# 使无人机攻击目标
def gameUAVAttack():
    # actionType = random.choice(['k', 'm'])
    actionType = 'k'        # 这里有键盘k 鼠标m 两种方式   这里只用键盘方式,防止鼠标点错
    if actionType == 'k':
        fk.fFakeTime('s', 0.2, 0.5)
        fk.fKeyDown('f')
        fk.fFakeTime('s', 0.2, 0.5)
        fk.fKeyUp('f')
        fk.fFakeTime('s', 0.2, 0.5)
    elif actionType == 'm':
        fk.fMoveTo(416, 199, 75, 7, gDuration, gDurationOffset)
        fk.fFakeTime('s', 0.4, 0.7)
        fk.fClickRight()
        fk.fFakeTime('s', 0.4, 0.7)
        fk.fMoveRel(94, 13, 50, 7, gDuration, gDurationOffset)
        fk.fFakeTime('s', 0.4, 0.7)
        fk.fClickLeft()
        fk.fFakeTime('s', 0.4, 0.7)

# 点击<挂舱中的无人机>
def gameClickUAVCabin():
    fk.fMoveTo(411, 177, 20, 4, gDuration, gDurationOffset)
    fk.fFakeTime('s', 0.4, 0.7)
    fk.fClickLeft()
    fk.fFakeTime('s', 0.4, 0.7)


class Farming( QMainWindow, Ui_Farming): 
    signalCrossThread = pyqtSignal(str, str)     #两个str参数,第一个接收信号类型,第二个接收信号内容

    def __init__(self,parent =None):
        super( Farming,self).__init__(parent)
        self.setupUi(self)

        # 打开配置文件,初始化界面
        self.leToken.setReadOnly(True)
        self.leToken2.setReadOnly(True)
        self.token = ''     # 创建一个变量用来存储token
        if os.path.exists( "./EVEFarming.ini"):
            try:
                iniFileDir = os.getcwd() + "\\"+ "EVEFarming.ini"
                with open( iniFileDir, 'r', encoding="utf-8") as iniFile:
                    iniDict = json.loads( iniFile.read())
                if iniDict:
                    self.leToken.setText(iniDict['token'])
                    self.leToken2.setText(iniDict['token2'])
                    self.token = iniDict['token']
                    self.token2 = iniDict['token2']

            except:
                QMessageBox.about( self, "提示", "打开初始化文件EVEFarming.ini异常, 软件关闭时会自动重新创建EVEFarming.ini文件")

        # 初始化twWindowList的表头
        windowListTitle = ['窗口名', '句柄', '状态', '参数']
        self.twWindowList.setColumnCount(len(windowListTitle))
        self.twWindowList.setHorizontalHeaderLabels(windowListTitle)
        self.twWindowList.setColumnWidth(3, 150)
        # 设置teLog只能显示n行, 超过n行时, 第1行会被删除
        self.teLog.document().setMaximumBlockCount(300)

        # 初始化声音测试的QComboBox
        self.cbSound.addItems(["特殊野怪 special", "错误提示 error"])

        # 注册一个全局快捷键,用于关闭音乐
        self.hotkey = SystemHotkey()
        self.hotkey.register(('control', 'f12'), callback=lambda x: self.mfStopSound())

    # 绑定槽函数
        self.btnBindWindow.clicked.connect(self.mfBindWindow)
        self.btnStart.clicked.connect(self.mfStart)
        self.btnStop.clicked.connect(self.mfStop)
        self.btnTest.clicked.connect(self.mfTest)
        self.btnGoHome.clicked.connect(self.mfGoHome)
        self.btnChangeToken.clicked.connect(self.mfChangeToken)
        self.btnChangeToken2.clicked.connect(self.mfChangeToken2)
        self.btnTestToken.clicked.connect(self.mfTestToken)
        self.btnTestToken2.clicked.connect(self.mfTestToken2)
        self.btnStopSound.clicked.connect(self.mfStopSound)
        self.btnHelp.clicked.connect(self.mfHelp)
        self.btnTestSound.clicked.connect(self.mfTestSound)

        self.signalCrossThread.connect( self.mfSignal)       # 处理子线程给主线程发的信号

    # 处理子线程给主线程发的信号, 信号signalType是字符串'QMessageBox' 'Display' 'State'
    def mfSignal( self, signalType, content):
        if signalType == 'State':
            pass

        elif signalType == 'Display':
            self.teLog.append( content)

        elif signalType == 'QMessageBox':
            QMessageBox.about( self, "提示", content)

        elif signalType == 'Sound':
            # 播放警报声音
            if content == 'special':
                url = QUrl.fromLocalFile( os.getcwd() + '/' + 'specialCreeper.mp3')
                if not os.path.exists(os.getcwd() + '/' + 'specialCreeper.mp3'):
                    QMessageBox.information(self, "提示", "未找到声音文件  " + os.getcwd() + '/' + 'specialCreeper.mp3')
                    return
            elif content == 'error':
                url = QUrl.fromLocalFile( os.getcwd() + '/' + 'error.wav')
                if not os.path.exists(os.getcwd() + '/' + 'error.wav'):
                    QMessageBox.information(self, "提示", "未找到声音文件  " + os.getcwd() + '/' + 'error.wav')
                    return

            mediaContent = QtMultimedia.QMediaContent(url)
            # --------------------------------------------------------------------------------------------------
            # 注意这里的player前面要加self.   把player加入到这个类中
            # 因为QtMultimedia.QMediaPlayer() 必须在app = QApplication(sys.argv)之后才能播放声音
            # QtMultimedia会在主线程里加一个timer来播放声音, 没有app = QApplication(sys.argv)就没有主线程,没有信号队列
            # 单独写一个QtMultimedia.QMediaPlayer()是不能播放的
            #---------------------------------------------------------------------------------------------------
            self.player = QtMultimedia.QMediaPlayer()
            self.player.setMedia(mediaContent)
            self.player.setVolume(100)
            self.player.play()     

        elif signalType == 'Push':
            pushTitle= content
            pushContent = content
            # 判断token是否有内容,没有内容则不发送
            if self.token:
                pushURL = 'http://www.pushplus.plus/send?token='+self.token+'&title='+pushTitle+'&content='+pushContent           
                result = requests.get(pushURL)
                result = result.json()
                if result['code'] != 200:
                    self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  pushPlus端口调用失败*****')
                    self.signalCrossThread.emit( 'Sound', 'error')      # 播放错误提示音
                
            # 判断token2是否有内容,没有内容则不发送
            if self.token2:
                pushURL2 = 'http://www.pushplus.plus/send?token='+self.token2+'&title='+pushTitle+'&content='+pushContent
                result2 = requests.get(pushURL2)
                result2 = result2.json()
                if result2['code'] != 200:
                    self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  pushPlus端口调用失败*****')
                    self.signalCrossThread.emit( 'Sound', 'error')      # 播放错误提示音


    # 停止正在播放的声音
    def mfStopSound(self):
        if hasattr(self, 'player'):         # 这个函数是判断类中是否有指定变量
            self.player.stop()
            self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  停止音乐播放')

    # 测试声音
    def mfTestSound(self):
        soundName = self.cbSound.currentText().split(' ')[1]
        # print( soundName)
        if soundName == 'special':
            self.signalCrossThread.emit( 'Sound', 'special')
        elif soundName == 'error':
            self.signalCrossThread.emit( 'Sound', 'error')


    # 使用帮助按钮
    def mfHelp(self):
        QMessageBox.information(self, '注意事项', '******启动脚本前,先检查游戏设置,游戏更新后,很多保存的设置会改变,尤其是保存的地点和快捷键\
                                \n1. 游戏主机输入法的默认模式选择*英语\
                                \n2. 挂舱中多放几个无人机,如果挂舱中的无人机被全部释放出来,在右键点击<挂舱中的无人机>后会出错.这一条在鼠标操作无人机选项时适用\
                                \n3. 需要设定<与失踪的无人机取得联系>快捷键为Shift + ]. 回收无人机功能已关闭\
                                \n4. 进入游戏之后,需要关闭广告,关闭联盟军团聊天窗口.在太空中收起<挂舱中的无人机>,打开<太空中的无人机>\
                                \n5. 星币提示框刚好和第6/7/8位置玩家列表重合,所有无法检测本地列表6/7/8位置玩家是白名还是红名\
                                \n6. 战斗时,设置默认环绕距离为*1km(原值为10km),这样在回收无人机时可能会更快\
                                \n7. pyautogui.FAILSAFE的值未设置,默认应该是True. 把鼠标移动到屏幕四个角,可以触发异常终止脚本运行.\
                                \n8. 返回空间站时,保存的地点命名为<HOME>或者任意四位大写字母\
                                \n9. 跳星带时,选择跃迁到20km,离星带远一点,防止被航母快速锁定\
                                \n10. 无人机挂舱太空中的无人机一栏要拉宽,使无人机状态文字显示出来.\
                                \n11. 总览中野怪名字一栏要拉宽,使名字显示更完整\
                                \n12. 分辨率调为1280*960,游戏中字体调为<小型>\
                                \n13. 2023年5月26日 UI改版,需要配合MyEVESetting界面使用\
                                ')

    # 修改pushplus Token
    def mfChangeToken(self):
        text, ok = QInputDialog.getText(self, '修改token', 'Enter your token:')
        if ok:
            self.leToken.setText(text)
            self.token = text

    # 修改pushplus Token 2
    def mfChangeToken2(self):
        text, ok = QInputDialog.getText(self, '修改token2', 'Enter your token:')
        if ok:
            self.leToken2.setText(text)
            self.token2 = text

    # 测试pushplus Token
    def mfTestToken(self):
        if self.token and self.leToken.text() and self.token == self.leToken.text():
            title = '测试推送功能,一定要打开内容查看'
            content = '请仔细检查发送时间以确定推送功能正常 -> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            pushURL = 'http://www.pushplus.plus/send?token='+self.token+'&title='+title+'&content='+content
            result = requests.get(pushURL)
            result = result.json()
            if result['code'] != 200:
                self.signalCrossThread.emit( 'Sound', 'error')      # 播放错误提示音
                QMessageBox.information(self, "提示", "pushplus接口调用失败,返回值 " + str(result['code']) +
                                        '\n\
                                        \n 200-执行成功; \
                                        \n 302-未登录; \
                                        \n 401-请求未授权; \
                                        \n 403-请求IP未授权; \
                                        \n 500-系统异常，请稍后再试; \
                                        \n 600-数据异常，操作失败; \
                                        \n 805-无权查看; \
                                        \n 888-积分不足，需要充值; \
                                        \n 900-用户账号使用受限; \
                                        \n 999-服务端验证错误; ')
                
            else:
                QMessageBox.information(self, "提示", "pushplus返回值200, 接口正常, 请查看微信通知")

        else:
            QMessageBox.information(self, "提示", "token错误, 请修改")

# 测试pushplus Token 2
    def mfTestToken2(self):
        if self.token2 and self.leToken2.text() and self.token2 == self.leToken2.text():
            title = '测试推送功能,一定要打开内容查看'
            content = '请仔细检查发送时间以确定推送功能正常 -> ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            pushURL = 'http://www.pushplus.plus/send?token='+self.token2+'&title='+title+'&content='+content
            result = requests.get(pushURL)
            result = result.json()
            if result['code'] != 200:
                self.signalCrossThread.emit( 'Sound', 'error')      # 播放错误提示音
                QMessageBox.information(self, "提示", "pushplus接口调用失败,返回值 " + str(result['code']) +
                                        '\n\
                                        \n 200-执行成功; \
                                        \n 302-未登录; \
                                        \n 401-请求未授权; \
                                        \n 403-请求IP未授权; \
                                        \n 500-系统异常，请稍后再试; \
                                        \n 600-数据异常，操作失败; \
                                        \n 805-无权查看; \
                                        \n 888-积分不足，需要充值; \
                                        \n 900-用户账号使用受限; \
                                        \n 999-服务端验证错误; ')
                
            else:
                QMessageBox.information(self, "提示", "pushplus返回值200, 接口正常, 请查看微信通知")

        else:
            QMessageBox.information(self, "提示", "token2错误, 请修改")



    def mfBindWindow(self):
        self.windowBind = Bind()
        self.windowBind.show()

        self.windowBind.signalToFarming.connect(self.mfRefreshWindowList)

    def mfRefreshWindowList(self, windowList):
        # print(windowList)
        # 清空twWindowList
        for i in range(0,self.twWindowList.rowCount()):
            self.twWindowList.removeRow(0)

        # 用windowBind.signalToFarming发送过来的消息刷新twWindowList内容
        for row, string in enumerate(windowList):
            self.twWindowList.insertRow( self.twWindowList.rowCount())
            title, hwnd = string.split('->')        # 获得窗口标题和句柄
            name = title.split('-')[0]              # 提取标题中'-'之前的部分
            self.twWindowList.setItem(row, 0, QTableWidgetItem(name))
            self.twWindowList.setItem(row, 1, QTableWidgetItem(hwnd))
            self.twWindowList.setItem(row, 2, QTableWidgetItem('已获得窗口句柄'))
            self.twWindowList.setItem(row, 3, QTableWidgetItem('输入星带范围,例如 1-30'))     # 已知最大的34个星带, 这个直接决定跃迁位置,很重要

    def mfStop(self):
        global ISRUN
        ISRUN = False
        self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  当前操作完成后,停止脚本')


    def mfStart(self):
        global ISRUN 
        ISRUN = True
        self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  5秒后开始执行脚本')
        QApplication.processEvents()
        # 本来想写多线程, 向radmin窗口发送消息的功能写不出来,放弃了
        # for rowIndex in range(0,self.twWindowList.rowCount()):
        #     hwnd = self.twWindowList.item(rowIndex, 1).text()
        #     singleWindowThreading = threading.Thread( target= self.mfRun, args=(rowIndex, hwnd))
        #     singleWindowThreading.start()
        #     self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  第' + str(rowIndex) + '行 句柄:' + hwnd + ' 创建线程成功')
        
        time.sleep(5)
        runThreading = threading.Thread( target= self.mfRun)
        runThreading.start()

    # 点击回家按钮,所有飞船回收无人机并回家
    def mfGoHome(self):
        # 未绑定游戏窗口
        if self.twWindowList.rowCount() == 0:
            self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  请先绑定游戏窗口')
            return

        runList = []        # 写一个字典的列表,用来存self.twWindowList里的信息,然后交给循坏去执行
        for row in range(self.twWindowList.rowCount()):
            tempDict = {}
            title = self.twWindowList.item(row, 0).text()
            hwnd = self.twWindowList.item(row, 1).text()
            tempDict.update({'title':title, 'hwnd':hwnd})
            runList.append(tempDict)

        for n in range(len(runList)):

            win32gui.SetForegroundWindow(runList[n]['hwnd'])
            time.sleep(1)       # 把窗口放到最前 和 对窗口进行截图 之间  加一个间隔
            # 先移动到空白的地方点一下,清除界面上打开的菜单
            fk.fMoveTo(143, 740, 90, 45, gDuration, gDurationOffset)       # 这个位置是在聊天记录框的下面
            # fk.fMoveTo(47, 266, 3, 70, gDuration, gDurationOffset)     # 这个位置是在本地聊天记录框里,要防止点击'EVE系统消息',否则会弹出星系信息. 总是找不到合适的位置,弃用 
            fk.fClickLeft()
            time.sleep(0.5)
            gameRetrieveUAV()
            fk.fFakeTime('s', 4, 5)
            gameGoHome()
            

#--------------------------------------------核心代码----------------------------------------------------------
    def mfTest(self):
        hwnd = self.twWindowList.item(0, 1).text()
        win32gui.SetForegroundWindow(hwnd)

        # # # a = fCheckImage(hwnd, 0,0,200,200,20,256,20,256,20,256)
        fCheckState(hwnd)
        # gameUAVAttack()
        # fScreenShot(hwnd)
        # gameRepairShip()
        # fCheckCreeper(hwnd)
        # # print(a)
        # # time.sleep(2)
        # gameGoHome()
        # print('over')
        # self.signalCrossThread.emit( 'Sound', 'special')
        # time.sleep(20)
        # self.player.stop()
        # self.signalCrossThread.emit( 'Push','hello word')
        # fCheckCreeper( hwnd)
        # gameLeaveStation()

        pass

    def mfRun(self):
        global ISRUN 
        if ISRUN == False:
            return
        
        # 未绑定游戏窗口
        if self.twWindowList.rowCount() == 0:
            self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  请先绑定游戏窗口')
            return

        beltNum = {}        # 用来记录每个窗口刷到第几个星带
        runList = []        # 写一个字典的列表,用来存self.twWindowList里的信息,然后交给循坏去执行
        for row in range(self.twWindowList.rowCount()):
            tempDict = {}
            title = self.twWindowList.item(row, 0).text()
            hwnd = self.twWindowList.item(row, 1).text()
            # self.twWindowList 第三列是状态,不需要获取信息
            param = self.twWindowList.item(row, 3).text()

            if param[0] == '输':        # '输入星带范围,例如 1-30' 的第一个字符
                self.signalCrossThread.emit( 'QMessageBox', '一定要正确填写刷哪几个星带,参数出错,脚本一定会崩溃! 格式例如: 1-30')
                return
            else:
                beltStart, beltEnd = param.split('-')[0], param.split('-')[1]

            tempDict.update({'title':title, 'hwnd':hwnd, 'beltStart':beltStart, 'beltEnd':beltEnd})
            runList.append(tempDict)
            beltNum.update({hwnd:beltStart})

        

        while( ISRUN == True):
            # print('in main loop')

            for n in range(len(runList)):
                if ISRUN == False:
                    return

                # print( runList[n]['title'], runList[n]['hwnd'], runList[n]['beltStart'], runList[n]['beltEnd'])
                win32gui.SetForegroundWindow(runList[n]['hwnd'])
                time.sleep(1)       # 把窗口放到最前 和 对窗口进行截图 之间  加一个间隔
                # 先移动到空白的地方点一下,清除界面上打开的菜单
                fk.fMoveTo(143, 740, 90, 45, gDuration, gDurationOffset)       # 这个位置是在聊天记录框的下面
                # fk.fMoveTo(47, 266, 3, 70, gDuration, gDurationOffset)     # 这个位置是在本地聊天记录框里,要防止点击'EVE系统消息',否则会弹出星系信息. 总是找不到合适的位置,弃用 
                fk.fClickLeft()
                time.sleep(0.5)
                state = fCheckState(runList[n]['hwnd'])
                # 截图错误时  state == False
                if state == False:
                    return
                
                # --------------------------------------开始操作----------------------------------------------
                if state['jump'] == True:
                    # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  跃迁')
                    continue

                if state['destroyed'] == True:
                    self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  舰船损毁')
                    # self.signalCrossThread.emit( 'Push', runList[n]['title'] + ' 舰船损毁')
                    self.signalCrossThread.emit( 'Sound', 'error')      # 播放错误提示音
                    continue

                # if state['disconnected'] == True:
                #     self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  掉线了')
                #     # self.signalCrossThread.emit( 'Push', runList[n]['title'] + ' 掉线了')
                #     # self.signalCrossThread.emit( 'Sound', 'error')      # 播放错误提示音
                #     continue

                if state['station'] == True:
                    if state['danger'] == True:
                        # 在站内,有危险,不操作
                        # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  有危险,不出站')
                        continue
                    
                    elif state['danger'] == False:
                        # 在站内,无危险,出站
                        # 判断会战模式
                        # print('battleMode', state['battleMode'])
                        if state['battleMode'] == False:
                            # 打开会战模式
                            # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  打开会战模式')
                            gameActivateBattleMode()

                        # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  修船')
                        gameRepairShip()    # 修船 2023年5月29日舰船维修已停用,函数中只保留了关闭小行星页面的功能
                        # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  出站')
                        gameLeaveStation()
                        
                        # 打开护盾
                        # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  打开护盾')
                        gameActivateShield()
                        gameClickShuaGuai()
                        gameClickUAVCabin()

                        # 起跳然后停止,使跃迁提示的字体从灰色变成纯白色
                        # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  起跳然后停止')
                        # 2023年5月29日先暂停此功能,缩短出站准备的时间
                        # gameJumpStop()

                        

                elif state['station'] == False:
                    if state['danger'] == True:
                        # 在太空,有危险,进站
                        self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  在太空,有危险,进站')
                        gameGoHome()
                        continue
                    
                    elif state['danger'] == False:
                        # 在太空,无危险
                        # 判断护盾和装甲值, 护盾过低则返回空间站
                        if state['damaged'] == True:
                            # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  护盾值过低,回空间站维修')
                            # 判断无人机是否释放
                            if state['UAVground'] == False:
                                gameRetrieveUAV()
                            gameGoHome()

                        if state['creep'] == True:
                            #在太空,无危险,有野怪
                            if state['UAVattack'] == True:
                                # 在太空,无危险,有野怪,无人机在战斗
                                # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  无人机战斗中')
                                continue

                            # 在太空,无危险,有野怪,无人机没有在战斗 
                            # 野怪距离过远,直接跳下一星带
                            if state['creepTooFar'] == True:
                                # 收回无人机,跳下一个星带
                                gameRetrieveUAV()
                                fk.fFakeTime('s', 3, 4)
                                # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  飞到星带 ' + str(beltNum[runList[n]['hwnd']]))
                                gameJumpTo(int(beltNum[runList[n]['hwnd']]))
                                # 计算下一次跳第几个星带
                                beltNum[runList[n]['hwnd']] = int(beltNum[runList[n]['hwnd']]) + 1
                                if int(beltNum[runList[n]['hwnd']]) == int(runList[n]['beltEnd']) + 1:
                                    beltNum[runList[n]['hwnd']] = runList[n]['beltStart']
                                continue    


                            # 这里很重要, 要写函数检测是什么野怪--------------------------------------------------
                            creeperType, creeperCharSet = fCheckCreeper(runList[n]['hwnd'])
                            if creeperType == False:      # 检测野怪类型失败
                                self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  检测野怪类型失败-------')
                                # gameGoHome()   这里不能回家,一是浪费时间,二是出站耗时太长,影响操作其他游戏窗口
                                # 这里改为跳到下一个星带
                                # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  飞到星带 ' + str(beltNum[runList[n]['hwnd']]))
                                gameJumpTo(int(beltNum[runList[n]['hwnd']]))
                                # 计算下一次跳第几个星带
                                beltNum[runList[n]['hwnd']] = int(beltNum[runList[n]['hwnd']]) + 1
                                if int(beltNum[runList[n]['hwnd']]) == int(runList[n]['beltEnd']) + 1:
                                    beltNum[runList[n]['hwnd']] = runList[n]['beltStart']
                                

                            elif creeperType == 'common':     # 普通野怪
                                # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  普通野怪  ' + ''.join(creeperCharSet))
                                # 环绕第一个野怪
                                # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  环绕第一个野怪')
                                gameLockTarget()
                                gameSelectFirstCreeper()
                                gameCirclingTarget()
                                # 释放无人机
                                # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  释放无人机')
                                gameReleaseUAV()
                                gameUAVAttack()
                                
                            elif creeperType == 'special':
                                self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  特殊野怪*****官员 ' + ''.join(creeperCharSet))
                                self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  位置在星带 -- ' + str(int(beltNum[runList[n]['hwnd']])-1))    
                                if self.cbSpecialPush.isChecked():
                                    # 两次推送提醒
                                    self.signalCrossThread.emit( 'Push', runList[n]['title'] + ' 星带' + str(int(beltNum[runList[n]['hwnd']])-1) + ' -> ' + ''.join(creeperCharSet))
                                    fk.fFakeTime('s', 1.5, 2)   
                                    self.signalCrossThread.emit( 'Push', runList[n]['title'] + ' 星带' + str(int(beltNum[runList[n]['hwnd']])-1) + ' -> ' + ''.join(creeperCharSet))

                                if self.cbSpecialSound.isChecked():
                                    self.signalCrossThread.emit( 'Sound', 'special')
                                # gameGoHome()   这里不能回家,一是浪费时间,二是出站耗时太长,影响操作其他游戏窗口
                                # 这里改为跳到下一个星带
                                # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  飞到星带 ' + str(beltNum[runList[n]['hwnd']]))
                                gameJumpTo(int(beltNum[runList[n]['hwnd']]))
                                # 计算下一次跳第几个星带
                                beltNum[runList[n]['hwnd']] = int(beltNum[runList[n]['hwnd']]) + 1
                                if int(beltNum[runList[n]['hwnd']]) == int(runList[n]['beltEnd']) + 1:
                                    beltNum[runList[n]['hwnd']] = runList[n]['beltStart']

                                # 判断跃迁是否成功,如果不成功则再次跃迁
                                fk.fMoveTo(143, 740, 90, 45, gDuration, gDurationOffset)       # 这个位置是在聊天记录框的下面
                                fk.fFakeTime('s', 3.5, 4)
                                emergencyState = fCheckState(runList[n]['hwnd'])
                                if emergencyState['jump'] == False:
                                    gameGoHome()
                                    fk.fMoveTo(143, 740, 90, 45, gDuration, gDurationOffset)       # 这个位置是在聊天记录框的下面
                                    fk.fFakeTime('s', 3.5, 4)
                                    emergencyState = fCheckState(runList[n]['hwnd'])
                                    if emergencyState['jump'] == False:
                                        gameGoHome()


                            elif creeperType == 'boss':
                                self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  特殊野怪*BOSS ' + ''.join(creeperCharSet))
                                self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  位置在星带 -- ' + str(int(beltNum[runList[n]['hwnd']])-1))    
                                if self.cbBossPush.isChecked():
                                    self.signalCrossThread.emit( 'Push', runList[n]['title'] + ' 星带' + str(int(beltNum[runList[n]['hwnd']])-1) + ' -> ' + ''.join(creeperCharSet))
                                if self.cbBossSound.isChecked():
                                    self.signalCrossThread.emit( 'Sound', 'special')

                                # 下面是遇到boss, 就像遇到普通野怪一样直接打
                                # 环绕第一个野怪
                                # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  环绕第一个野怪')
                                gameLockTarget()
                                gameSelectFirstCreeper()
                                gameCirclingTarget()
                                # 释放无人机
                                # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  释放无人机')
                                gameReleaseUAV()
                                gameUAVAttack()


                            elif creeperType == 'barge':
                                if self.cbBargePush.isChecked():
                                    self.signalCrossThread.emit( 'Push', runList[n]['title'] + ' 星带' + str(beltNum[runList[n]['hwnd']]) + ' -> ' + ''.join(creeperCharSet))
                                if self.cbBargeSound.isChecked():
                                    self.signalCrossThread.emit( 'Sound', 'special')

                                self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  矿船 ' + ''.join(creeperCharSet))
                                self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  位置在星带 -- ' + str(int(beltNum[runList[n]['hwnd']])-1))    

                                # 环绕第一个野怪
                                # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  环绕第一个野怪')
                                gameLockTarget()
                                gameSelectFirstCreeper()
                                gameCirclingTarget()
                                # 释放无人机
                                # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  释放无人机')
                                gameReleaseUAV()
                                gameUAVAttack()

                            elif creeperType == 'skipped':
                                # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  打不过的野怪 ' + ''.join(creeperCharSet))
                                # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  位置在星带 -- ' + str(int(beltNum[runList[n]['hwnd']])-1))    
                                if self.cbSkippedPush.isChecked():
                                    self.signalCrossThread.emit( 'Push', runList[n]['title'] + ' 星带' + str(int(beltNum[runList[n]['hwnd']])-1) + ' -> ' + ''.join(creeperCharSet))
                                if self.cbSkippedSound.isChecked():
                                    self.signalCrossThread.emit( 'Sound', 'special')

                                # gameGoHome()   这里不能回家,一是浪费时间,二是出站耗时太长,影响操作其他游戏窗口
                                # 这里改为跳到下一个星带
                                # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  飞到星带 ' + str(beltNum[runList[n]['hwnd']]))
                                gameJumpTo(int(beltNum[runList[n]['hwnd']]))
                                # 计算下一次跳第几个星带
                                beltNum[runList[n]['hwnd']] = int(beltNum[runList[n]['hwnd']]) + 1
                                if int(beltNum[runList[n]['hwnd']]) == int(runList[n]['beltEnd']) + 1:
                                    beltNum[runList[n]['hwnd']] = runList[n]['beltStart']

                                # 判断跃迁是否成功,如果不成功则再次跃迁
                                fk.fMoveTo(143, 740, 90, 45, gDuration, gDurationOffset)       # 这个位置是在聊天记录框的下面
                                fk.fFakeTime('s', 3.5, 4)
                                emergencyState = fCheckState(runList[n]['hwnd'])
                                if emergencyState['jump'] == False:
                                    gameGoHome()
                                    fk.fMoveTo(143, 740, 90, 45, gDuration, gDurationOffset)       # 这个位置是在聊天记录框的下面
                                    fk.fFakeTime('s', 3.5, 4)
                                    emergencyState = fCheckState(runList[n]['hwnd'])
                                    if emergencyState['jump'] == False:
                                        gameGoHome()
                                

                        elif state['creep'] == False:
                            # 在太空,无危险,没有野怪
                            # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  与失踪的无人机取得联系')
                            # gameContactUAV()        # 与失踪的无人机取得联系, 先把这个功能取消
                            # fk.fFakeTime('s', 2, 2.5)

                            if state['UAVground'] == True:
                                # 在太空,无危险,没有野怪,无人机未释放
                                # 跳到下一个星带
                                # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  飞到星带 ' + str(beltNum[runList[n]['hwnd']]))
                                gameJumpTo(int(beltNum[runList[n]['hwnd']]))
                                # 计算下一次跳第几个星带
                                beltNum[runList[n]['hwnd']] = int(beltNum[runList[n]['hwnd']]) + 1
                                if int(beltNum[runList[n]['hwnd']]) == int(runList[n]['beltEnd']) + 1:
                                    beltNum[runList[n]['hwnd']] = runList[n]['beltStart']    
                                # 调试代码
                                # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  测试 矿船位置在 ' + str(int(beltNum[runList[n]['hwnd']])-4) + '--' + str(beltNum[runList[n]['hwnd']]) + '附近')    
                                # print('num',beltNum[runList[n]['hwnd']])
                                # print('start',runList[n]['beltStart'])
                                # print('end',runList[n]['beltEnd'])

                            elif state['UAVground'] == False:
                                # 在太空,无危险,没有野怪,无人机未收回
                                # 回收无人机
                                # self.signalCrossThread.emit( 'Display', datetime.datetime.now().strftime('%H:%M:%S') + '  ' + runList[n]['title'] + '  回收无人机')
                                gameRetrieveUAV()

                fk.fFakeTime('s', 0.5, 1)         # 一个窗口的操作完毕后,等待一下再进行下一个窗口的操作     
                    

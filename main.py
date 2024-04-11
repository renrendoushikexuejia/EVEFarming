import sys,threading,os,json,datetime,time
from PyQt5.QtWidgets import QApplication,QMessageBox
from Farming import Farming



#主程序入口
if __name__ == "__main__":
    app = QApplication(sys.argv)
    windowFarming = Farming()
    windowFarming.show()

    appExit = app.exec_()
    # 退出程序之前,保存界面上的设置
    tempDict = { 'token':windowFarming.leToken.text(), 'token2':windowFarming.leToken2.text()}
    saveIniJson = json.dumps( tempDict, indent=4)
    try:
        saveIniFile = open( "./EVEFarming.ini", "w",  encoding="utf-8")
        saveIniFile.write( saveIniJson)
        saveIniFile.close()
    except:
        QMessageBox.about( windowFarming, "提示", "保存配置文件EVEFarming.ini失败")

    # 这一句特别重要, 程序是两个线程在运行, 关闭窗口只能结束主线程, 子线程还在运行. 
    # 创建子线程的标志ISRUN 一定要改成0, 子线程在检测ISRUN==0之后,就不再用Timer创建新的线程了
    # 下面两行是为了让 ISRUN = 0  不知道哪一行会起作用. 有空测试一下  
    windowFarming.mfStop()      
    ISRUN = 0

    sys.exit( appExit)
# sys.exit(app.exec_())  
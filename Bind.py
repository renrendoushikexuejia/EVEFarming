from PyQt5.QtWidgets import QMainWindow,QCheckBox,QListWidgetItem
from PyQt5.QtCore import pyqtSignal
import win32gui
from Ui_Bind import Ui_Bind

class Bind( QMainWindow, Ui_Bind): 
    signalToFarming = pyqtSignal(list)

    def __init__(self,parent =None):
        super( Bind,self).__init__(parent)
        self.setupUi(self)

        # 定义一个字典,用来保存所有找到的窗口
        self.hwndDict = {}

        #获得所有打开的窗口的句柄和名称，存在hwndDict。在win32gui.EnumWindows(getHwnd, 0)中调用
        def getHwnd(hwnd, mouse):
            if win32gui.IsWindow(hwnd) and win32gui.IsWindowEnabled(hwnd) and win32gui.IsWindowVisible(hwnd):
                self.hwndDict.update({hwnd:win32gui.GetWindowText(hwnd)})

            # 刷新窗口列表框
        def mfRefresh():
            self.lwWindows.clear()

            win32gui.EnumWindows(getHwnd, 0)
            for k, t in self.hwndDict.items():
                # if t != '' and t != 'Microsoft Store' and t != 'Microsoft Text Input Application' \
                # and t != 'Windows Shell Experience 主机' and t != 'Program Manager' \
                # and t != '设置' and t != '计算器':               #去除title为空 和无用的句柄
                if 'Full Control' in t:     # radmin的窗口名中有字符串'Full Control'
                    tempStr = t + '->' + str(k)
                    tempCheckBox = QCheckBox( tempStr)
                    tempItem = QListWidgetItem()
                    self.lwWindows.addItem( tempItem)
                    self.lwWindows.setItemWidget( tempItem, tempCheckBox)

            self.hwndDict.clear()       # 刷新之后记得清空全局字典, 以便下次刷新


        def mfOK():
            #获得ListWidght选中项组成的字典
            tempList = list()
            for i in range( 0, self.lwWindows.count()):
                if self.lwWindows.itemWidget( self.lwWindows.item(i)).isChecked():
                    tempList.append( self.lwWindows.itemWidget( self.lwWindows.item(i)).text())
            
            # print(tempList)
            self.signalToFarming.emit( tempList)
            self.close()

        #绑定槽函数
        self.btnRefresh.clicked.connect( mfRefresh)
        self.btnOK.clicked.connect( mfOK)

        mfRefresh()     # 类初始化完成后,先调用一次用来刷新界面
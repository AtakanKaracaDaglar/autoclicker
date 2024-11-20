import cv2
import numpy as np
import pyautogui
import ctypes
import time
from PyQt5 import QtWidgets, QtCore, QtGui
import threading

class AutoClickerGUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.running = threading.Event()  # Tıklama işlemi kontrolü için threading.Event nesnesi
        self.region_coords = None

    def initUI(self):
        self.setGeometry(100, 100, 500, 500)
        self.setWindowTitle('Auto Clicker with Color Detection')
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)  # Uygulamanın her zaman önde olmasını sağla

        # Delay section
        self.delay_label = QtWidgets.QLabel('Tıklama Gecikmesi:', self)
        self.delay_label.move(20, 20)
        self.delay_seconds_label = QtWidgets.QLabel('Saniye:', self)
        self.delay_seconds_label.setGeometry(200, 20, 50, 20)
        self.delay_seconds_input = QtWidgets.QLineEdit(self)
        self.delay_seconds_input.setGeometry(260, 20, 40, 20)
        self.delay_seconds_input.setPlaceholderText('Saniye')
        
        self.delay_milliseconds_label = QtWidgets.QLabel('Milisaniye:', self)
        self.delay_milliseconds_label.setGeometry(320, 20, 70, 20)
        self.delay_milliseconds_input = QtWidgets.QLineEdit(self)
        self.delay_milliseconds_input.setGeometry(400, 20, 40, 20)
        self.delay_milliseconds_input.setPlaceholderText('ms')

        # Click options
        self.click_option_label = QtWidgets.QLabel('Tıklama Türü:', self)
        self.click_option_label.move(20, 60)
        self.click_option = QtWidgets.QComboBox(self)
        self.click_option.setGeometry(200, 60, 100, 20)
        self.click_option.addItems(['Sol Tık', 'Sağ Tık'])

        # Click repeat options
        self.click_repeat_label = QtWidgets.QLabel('Tıklama Tekrarı:', self)
        self.click_repeat_label.move(20, 100)
        self.click_repeat_once = QtWidgets.QRadioButton('Belirli Sayı', self)
        self.click_repeat_once.setGeometry(200, 100, 100, 20)
        self.click_repeat_until_stopped = QtWidgets.QRadioButton('Durdurulana Kadar', self)
        self.click_repeat_until_stopped.setGeometry(200, 130, 150, 20)
        self.click_repeat_group = QtWidgets.QButtonGroup(self)
        self.click_repeat_group.addButton(self.click_repeat_once)
        self.click_repeat_group.addButton(self.click_repeat_until_stopped)
        self.click_repeat_once.setChecked(True)

        # Number of clicks input
        self.click_count_label = QtWidgets.QLabel('Tıklama Sayısı:', self)
        self.click_count_label.setGeometry(20, 170, 100, 20)
        self.click_count_input = QtWidgets.QLineEdit(self)
        self.click_count_input.setGeometry(200, 170, 100, 20)
        self.click_count_input.setDisabled(False)
        self.click_repeat_once.toggled.connect(self.toggle_click_count_input)

        # Color selection
        self.color_label = QtWidgets.QLabel('Renk Seçimi (HSV):', self)
        self.color_label.move(20, 210)
        self.color_input = QtWidgets.QLineEdit(self)
        self.color_input.setGeometry(200, 210, 100, 20)
        self.color_input.setPlaceholderText('Örn: 40,40,40 - 80,255,255')
        self.color_pick_button = QtWidgets.QPushButton('Renk Seç', self)
        self.color_pick_button.setGeometry(320, 210, 100, 30)
        self.color_pick_button.clicked.connect(self.pick_color)

        # Region selection checkbox
        self.region_checkbox = QtWidgets.QCheckBox('Belirli bir bölgeyi seç', self)
        self.region_checkbox.setGeometry(20, 260, 200, 20)
        self.region_checkbox.stateChanged.connect(self.toggle_region_selection)

        # Region coordinates inputs
        self.region_coords_label = QtWidgets.QLabel('Bölgeyi Seçin:', self)
        self.region_coords_label.setGeometry(20, 290, 200, 20)
        self.region_select_button = QtWidgets.QPushButton('Bölge Seç', self)
        self.region_select_button.setGeometry(200, 290, 100, 30)
        self.region_select_button.setDisabled(True)
        self.region_select_button.clicked.connect(self.select_region)

        # Start and Stop buttons
        self.start_button = QtWidgets.QPushButton('Başlat/Durdur (F6)', self)
        self.start_button.setGeometry(170, 350, 150, 30)
        self.start_button.clicked.connect(self.toggle_clicker)

        # Status label
        self.status_label = QtWidgets.QLabel('Durum: Durduruldu', self)
        self.status_label.setGeometry(170, 400, 200, 30)

        # Shortcuts for start and stop
        self.start_stop_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence('F6'), self)
        self.start_stop_shortcut.activated.connect(self.toggle_clicker)

        # Safety shutdown shortcut
        self.safety_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence('F'), self)
        self.safety_shortcut.activated.connect(self.safety_shutdown)

        self.show()

    def toggle_click_count_input(self):
        self.click_count_input.setDisabled(not self.click_repeat_once.isChecked())

    def toggle_region_selection(self, state):
        self.region_select_button.setDisabled(state == QtCore.Qt.Unchecked)

    def toggle_clicker(self):
        if self.running.is_set():
            self.stop_clicker()
        else:
            self.start_clicker()

    def start_clicker(self):
        try:
            seconds = self.delay_seconds_input.text()
            milliseconds = self.delay_milliseconds_input.text()
            if not seconds and milliseconds:
                self.delay = float(milliseconds) / 1000.0
            else:
                self.delay = float(seconds) + (float(milliseconds) / 1000.0 if milliseconds else 0)
            if self.delay < 0:
                raise ValueError("Gecikme süresi negatif olamaz.")
            self.color_range = self.parse_color_input(self.color_input.text())
            if not self.color_range:
                raise ValueError("Renk aralığı geçersiz.")
            if self.click_repeat_once.isChecked():
                self.click_count = int(self.click_count_input.text())
                if self.click_count <= 0:
                    raise ValueError("Tıklama sayısı pozitif olmalı.")
            if self.region_checkbox.isChecked() and not hasattr(self, 'region_coords'):
                raise ValueError('Bölge seçilmedi.')
            self.running.set()  # Tıklama işlemini başlat
            self.status_label.setText('Durum: Çalışıyor')
            threading.Thread(target=self.auto_clicker, daemon=True).start()
        except ValueError as e:
            QtWidgets.QMessageBox.warning(self, 'Hata', str(e))

    def stop_clicker(self):
        self.running.clear()  # Tıklama işlemini durdur
        self.status_label.setText('Durum: Durduruldu')

    def safety_shutdown(self):
        self.running.clear()  # Tıklama işlemini durdur
        self.status_label.setText('Durum: Güvenlik Nedeniyle Durduruldu')
        QtWidgets.QMessageBox.information(self, 'Güvenlik', 'Program güvenlik amacıyla kapatıldı.')
        self.close()

    def parse_color_input(self, color_text):
        try:
            parts = color_text.split('-')
            lower = np.array([int(x) for x in parts[0].split(',')])
            upper = np.array([int(x) for x in parts[1].split(',')])
            return lower, upper
        except:
            return None

    def pick_color(self):
        try:
            screenshot = pyautogui.screenshot()
            screenshot = np.array(screenshot)
            screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB)

            def mouse_callback(event, x, y, flags, param):
                if event == cv2.EVENT_LBUTTONDOWN:
                    pixel = screenshot[y, x]
                    hsv_pixel = cv2.cvtColor(np.uint8([[pixel]]), cv2.COLOR_RGB2HSV)[0][0]
                    lower_hsv = np.array([35, 100, 100])  # Açık yeşil ve parlayan renk aralığının alt sınırı
                    upper_hsv = np.array([85, 255, 255])  # Açık yeşil ve parlayan renk aralığının üst sınırı
                    self.color_input.setText(f'{lower_hsv[0]},{lower_hsv[1]},{lower_hsv[2]} - {upper_hsv[0]},{upper_hsv[1]},{upper_hsv[2]}')
                    cv2.setMouseCallback('Renk Seçimi', lambda *args: None)
                    cv2.destroyAllWindows()

            cv2.imshow('Renk Seçimi', screenshot)
            cv2.setMouseCallback('Renk Seçimi', mouse_callback)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Hata', f'Renk seçimi sırasında bir hata oluştu: {str(e)}')

    def select_region(self):
        try:
            region = pyautogui.screenshot()
            region = np.array(region)
            region = cv2.cvtColor(region, cv2.COLOR_BGR2RGB)

            r = cv2.selectROI('Bölge Seçimi', region, fromCenter=False, showCrosshair=True)
            cv2.destroyAllWindows()
            if r != (0, 0, 0, 0):
                self.region_coords = r
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Hata', f'Bölge seçiminde bir hata oluştu: {str(e)}')

    def auto_clicker(self):
        while self.running.is_set():
            try:
                if self.region_checkbox.isChecked() and hasattr(self, 'region_coords'):
                    x, y, w, h = self.region_coords
                    screenshot = pyautogui.screenshot(region=(x, y, w, h))
                    region_offset_x, region_offset_y = x, y
                else:
                    screenshot = pyautogui.screenshot()

                frame = np.array(screenshot)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                lower = np.array([35, 100, 100])  # Açık yeşil ve parlayan renk aralığının alt sınırı
                upper = np.array([85, 255, 255])  # Açık yeşil ve parlayan renk aralığının üst sınırı
                hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
                mask = cv2.inRange(hsv, lower, upper)

                contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area > 300:
                        x, y, w, h = cv2.boundingRect(contour)
                        if not self.running.is_set():  # Durumu tekrar kontrol et
                            return
                        click_x = x + w // 2 + (region_offset_x if self.region_checkbox.isChecked() else 0)
                        click_y = y + h // 2 + (region_offset_y if self.region_checkbox.isChecked() else 0)
                        ctypes.windll.user32.SetCursorPos(click_x, click_y)
                        ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)  # Mouse left button down
                        ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)  # Mouse left button up
                        if self.click_repeat_once.isChecked():
                            self.click_count -= 1
                            if self.click_count <= 0:
                                self.running.clear()
                        break

                time.sleep(self.delay / 10)
                self.status_label.setText(f'Sleep süresi: {self.delay} saniye')
            except pyautogui.FailSafeException:
                QtWidgets.QMessageBox.warning(self, 'Durduruldu', 'PyAutoGUI failsafe etkinleştirildi.')
                self.running.clear()
                break
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, 'Hata', f'Tıklama sırasında bir hata oluştu: {str(e)}')
                self.running.clear()

    def get_click_button(self):
        return 'left' if self.click_option.currentText() == 'Sol Tık' else 'right'

if __name__ == '__main__':
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = AutoClickerGUI()
    sys.exit(app.exec_())

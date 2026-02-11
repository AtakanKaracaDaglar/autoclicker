import sys
import cv2
import numpy as np
import pyautogui
import time
from PyQt5 import QtWidgets, QtCore, QtGui
import threading
import keyboard


class StatusSignal(QtCore.QObject):
    """Thread-safe signal for updating GUI from background threads."""
    update_status = QtCore.pyqtSignal(str)
    show_warning = QtCore.pyqtSignal(str, str)
    request_start = QtCore.pyqtSignal()
    request_stop = QtCore.pyqtSignal()


class AutoClickerGUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.signals = StatusSignal()
        self.signals.update_status.connect(self._update_status_label)
        self.signals.show_warning.connect(self._show_warning)
        self.signals.request_start.connect(self.start_clicker)
        self.signals.request_stop.connect(self.stop_clicker)
        self.running = threading.Event()
        self.region_coords = None
        self.click_count = 0
        self.delay = 0.1
        self.color_range = None
        # Snapshot of settings taken at start time (thread-safe)
        self._use_color = False
        self._use_repeat_count = False
        self._click_button = 'left'
        self._use_region = False
        self.initUI()
        self._register_hotkeys()

    def initUI(self):
        self.setWindowTitle('Auto Clicker — Renk Algılama ile Otomatik Tıklama')
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(480)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setSpacing(12)

        # --- Gecikme Ayarları ---
        delay_group = QtWidgets.QGroupBox('⏱ Gecikme Ayarları')
        delay_layout = QtWidgets.QHBoxLayout()
        self.delay_seconds_input = QtWidgets.QSpinBox()
        self.delay_seconds_input.setRange(0, 3600)
        self.delay_seconds_input.setSuffix(' sn')
        self.delay_seconds_input.setValue(0)
        self.delay_milliseconds_input = QtWidgets.QSpinBox()
        self.delay_milliseconds_input.setRange(0, 999)
        self.delay_milliseconds_input.setSuffix(' ms')
        self.delay_milliseconds_input.setValue(100)
        delay_layout.addWidget(QtWidgets.QLabel('Saniye:'))
        delay_layout.addWidget(self.delay_seconds_input)
        delay_layout.addWidget(QtWidgets.QLabel('Milisaniye:'))
        delay_layout.addWidget(self.delay_milliseconds_input)
        delay_group.setLayout(delay_layout)
        main_layout.addWidget(delay_group)

        # --- Tıklama Ayarları ---
        click_group = QtWidgets.QGroupBox('🖱 Tıklama Ayarları')
        click_layout = QtWidgets.QFormLayout()

        self.click_option = QtWidgets.QComboBox()
        self.click_option.addItems(['Sol Tık', 'Sağ Tık'])
        click_layout.addRow('Tıklama Türü:', self.click_option)

        repeat_layout = QtWidgets.QHBoxLayout()
        self.click_repeat_once = QtWidgets.QRadioButton('Belirli Sayı')
        self.click_repeat_until_stopped = QtWidgets.QRadioButton('Durdurulana Kadar')
        self.click_repeat_group = QtWidgets.QButtonGroup(self)
        self.click_repeat_group.addButton(self.click_repeat_once)
        self.click_repeat_group.addButton(self.click_repeat_until_stopped)
        self.click_repeat_until_stopped.setChecked(True)
        repeat_layout.addWidget(self.click_repeat_once)
        repeat_layout.addWidget(self.click_repeat_until_stopped)
        click_layout.addRow('Tekrar Modu:', repeat_layout)

        self.click_count_input = QtWidgets.QSpinBox()
        self.click_count_input.setRange(1, 999999)
        self.click_count_input.setValue(10)
        self.click_count_input.setDisabled(True)
        self.click_repeat_once.toggled.connect(self.toggle_click_count_input)
        click_layout.addRow('Tıklama Sayısı:', self.click_count_input)

        click_group.setLayout(click_layout)
        main_layout.addWidget(click_group)

        # --- Renk Ayarları ---
        color_group = QtWidgets.QGroupBox('🎨 Renk Algılama (opsiyonel — boş bırakılırsa fare konumunda tıklar)')
        color_layout = QtWidgets.QHBoxLayout()
        self.color_input = QtWidgets.QLineEdit()
        self.color_input.setPlaceholderText('Örn: 40,40,40 - 80,255,255')
        self.color_pick_button = QtWidgets.QPushButton('🔍 Ekrandan Renk Seç')
        self.color_pick_button.clicked.connect(self.pick_color)
        color_layout.addWidget(self.color_input, stretch=1)
        color_layout.addWidget(self.color_pick_button)
        color_group.setLayout(color_layout)
        main_layout.addWidget(color_group)

        # --- Bölge Seçimi ---
        region_group = QtWidgets.QGroupBox('📐 Bölge Seçimi')
        region_layout = QtWidgets.QHBoxLayout()
        self.region_checkbox = QtWidgets.QCheckBox('Belirli bir bölgeyi tara')
        self.region_checkbox.stateChanged.connect(self.toggle_region_selection)
        self.region_select_button = QtWidgets.QPushButton('📌 Bölge Seç')
        self.region_select_button.setDisabled(True)
        self.region_select_button.clicked.connect(self.select_region)
        self.region_info_label = QtWidgets.QLabel('Bölge seçilmedi')
        self.region_info_label.setStyleSheet('color: gray; font-style: italic;')
        region_layout.addWidget(self.region_checkbox)
        region_layout.addWidget(self.region_select_button)
        region_layout.addWidget(self.region_info_label, stretch=1)
        region_group.setLayout(region_layout)
        main_layout.addWidget(region_group)

        # --- Kontrol Butonları ---
        control_layout = QtWidgets.QHBoxLayout()
        self.start_button = QtWidgets.QPushButton('▶ Başlat (F6)')
        self.start_button.setMinimumHeight(40)
        self.start_button.setStyleSheet(
            'background-color: #4CAF50; color: white; font-weight: bold;'
            'font-size: 14px; border-radius: 6px;'
        )
        self.start_button.clicked.connect(self.start_clicker)

        self.stop_button = QtWidgets.QPushButton('⏹ Durdur (F7)')
        self.stop_button.setMinimumHeight(40)
        self.stop_button.setStyleSheet(
            'background-color: #f44336; color: white; font-weight: bold;'
            'font-size: 14px; border-radius: 6px;'
        )
        self.stop_button.clicked.connect(self.stop_clicker)

        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)
        main_layout.addLayout(control_layout)

        # --- Durum Çubuğu ---
        self.status_label = QtWidgets.QLabel('⏸ Durum: Bekleniyor')
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setStyleSheet(
            'font-size: 13px; padding: 6px; background-color: #333;'
            'color: #eee; border-radius: 4px;'
        )
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)

        # Keyboard shortcuts (in-app, when window focused)
        QtWidgets.QShortcut(QtGui.QKeySequence('F6'), self).activated.connect(self.start_clicker)
        QtWidgets.QShortcut(QtGui.QKeySequence('F7'), self).activated.connect(self.stop_clicker)

        self.show()

    # --- Hotkey Registration (global, event-based — no CPU burn) ---
    def _register_hotkeys(self):
        keyboard.add_hotkey('f6', lambda: self.signals.request_start.emit())
        keyboard.add_hotkey('f7', lambda: self.signals.request_stop.emit())

    # --- Thread-safe GUI helpers ---
    @QtCore.pyqtSlot(str)
    def _update_status_label(self, text):
        self.status_label.setText(text)

    @QtCore.pyqtSlot(str, str)
    def _show_warning(self, title, message):
        QtWidgets.QMessageBox.warning(self, title, message)

    # --- Toggles ---
    def toggle_click_count_input(self):
        self.click_count_input.setDisabled(not self.click_repeat_once.isChecked())

    def toggle_region_selection(self, state):
        self.region_select_button.setDisabled(state == QtCore.Qt.Unchecked)

    # --- Start / Stop ---
    def start_clicker(self):
        if self.running.is_set():
            return  # Zaten çalışıyor

        try:
            seconds = self.delay_seconds_input.value()
            milliseconds = self.delay_milliseconds_input.value()
            self.delay = seconds + (milliseconds / 1000.0)
            if self.delay < 0.01:
                self.delay = 0.01  # Minimum 10ms

            color_text = self.color_input.text().strip()
            if color_text:
                self.color_range = self.parse_color_input(color_text)
                if not self.color_range:
                    raise ValueError("Renk aralığı formatı hatalı.\nÖrnek: 40,40,40 - 80,255,255")
                self._use_color = True
            else:
                self.color_range = None
                self._use_color = False

            # Thread-safe: Ayarları başlatma anında snapshot al
            self._use_repeat_count = self.click_repeat_once.isChecked()
            self._click_button = 'left' if self.click_option.currentText() == 'Sol Tık' else 'right'
            self._use_region = self.region_checkbox.isChecked()

            if self._use_repeat_count:
                self.click_count = self.click_count_input.value()
                if self.click_count <= 0:
                    raise ValueError("Tıklama sayısı en az 1 olmalı.")

            if self._use_region and self.region_coords is None:
                raise ValueError('Önce bir bölge seçmelisiniz.')

            self.running.set()
            self.status_label.setText('🟢 Durum: Çalışıyor')
            self.start_button.setEnabled(False)
            threading.Thread(target=self.auto_clicker, daemon=True).start()
        except ValueError as e:
            QtWidgets.QMessageBox.warning(self, 'Hata', str(e))

    def stop_clicker(self):
        self.running.clear()
        self.status_label.setText('⏸ Durum: Durduruldu')
        self.start_button.setEnabled(True)

    # --- Color Parsing ---
    def parse_color_input(self, color_text):
        try:
            parts = color_text.split('-')
            if len(parts) != 2:
                return None
            lower = np.array([int(x.strip()) for x in parts[0].split(',')])
            upper = np.array([int(x.strip()) for x in parts[1].split(',')])
            if lower.shape != (3,) or upper.shape != (3,):
                return None
            return lower, upper
        except (ValueError, IndexError):
            return None

    # --- Color Picker (threaded to not block Qt) ---
    def pick_color(self):
        threading.Thread(target=self._pick_color_worker, daemon=True).start()

    def _pick_color_worker(self):
        try:
            screenshot = pyautogui.screenshot()
            screenshot = np.array(screenshot)  # RGB from pyautogui
            display_img = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)

            picked = {'done': False}

            def mouse_callback(event, x, y, flags, param):
                if event == cv2.EVENT_LBUTTONDOWN:
                    pixel_rgb = screenshot[y, x]
                    hsv_pixel = cv2.cvtColor(
                        np.uint8([[pixel_rgb]]), cv2.COLOR_RGB2HSV
                    )[0][0]
                    lower_hsv = np.clip(hsv_pixel - np.array([10, 50, 50]), 0, 255)
                    upper_hsv = np.clip(hsv_pixel + np.array([10, 50, 50]), 0, 255)
                    result = (
                        f'{lower_hsv[0]},{lower_hsv[1]},{lower_hsv[2]} - '
                        f'{upper_hsv[0]},{upper_hsv[1]},{upper_hsv[2]}'
                    )
                    # Thread-safe: signal ile QLineEdit'e yaz
                    self.signals.update_status.emit(f'🎨 Renk seçildi: {result}')
                    # QLineEdit thread-safe değil, QMetaObject kullan
                    QtCore.QMetaObject.invokeMethod(
                        self.color_input, "setText",
                        QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, result)
                    )
                    picked['done'] = True

            cv2.imshow('Renk Secimi - Tikla', display_img)
            cv2.setMouseCallback('Renk Secimi - Tikla', mouse_callback)

            while not picked['done']:
                key = cv2.waitKey(100)
                if key == 27:  # ESC tuşu
                    break
            cv2.destroyAllWindows()
        except Exception as e:
            self.signals.show_warning.emit('Hata', f'Renk seçimi hatası: {e}')

    # --- Region Selector (threaded to not block Qt) ---
    def select_region(self):
        threading.Thread(target=self._select_region_worker, daemon=True).start()

    def _select_region_worker(self):
        try:
            screenshot = pyautogui.screenshot()
            screenshot = np.array(screenshot)
            display_img = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)

            r = cv2.selectROI('Bolge Secimi', display_img, fromCenter=False, showCrosshair=True)
            cv2.destroyAllWindows()
            if r != (0, 0, 0, 0):
                self.region_coords = r
                self.signals.update_status.emit(f'📐 Bölge: x={r[0]}, y={r[1]}, {r[2]}x{r[3]}')
                QtCore.QMetaObject.invokeMethod(
                    self.region_info_label, "setText",
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, f'Bölge: x={r[0]}, y={r[1]}, {r[2]}x{r[3]}')
                )
            else:
                self.region_coords = None
                QtCore.QMetaObject.invokeMethod(
                    self.region_info_label, "setText",
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, 'Bölge seçilmedi')
                )
        except Exception as e:
            self.signals.show_warning.emit('Hata', f'Bölge seçim hatası: {e}')

    # --- Main Auto Clicker Loop ---
    def auto_clicker(self):
        try:
            while self.running.is_set():
                # Renk seçilmediyse → mevcut fare konumunda tıkla
                if not self._use_color:
                    pyautogui.click(button=self._click_button)

                    if self._use_repeat_count:
                        self.click_count -= 1
                        if self.click_count <= 0:
                            self.running.clear()
                            self.signals.update_status.emit('✅ Tamamlandı')
                            break
                        self.signals.update_status.emit(
                            f'🟢 Tıklandı — Kalan: {self.click_count}'
                        )
                    else:
                        self.signals.update_status.emit(
                            f'🟢 Tıklanıyor... (gecikme: {self.delay:.2f}s)'
                        )
                    time.sleep(self.delay)
                    continue

                # Renk seçildiyse → ekran tarayarak rengi bul ve tıkla
                region_offset_x = 0
                region_offset_y = 0

                if self._use_region and self.region_coords is not None:
                    rx, ry, rw, rh = self.region_coords
                    screenshot = pyautogui.screenshot(region=(rx, ry, rw, rh))
                    region_offset_x, region_offset_y = rx, ry
                else:
                    screenshot = pyautogui.screenshot()

                frame = np.array(screenshot)
                hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)

                lower, upper = self.color_range
                mask = cv2.inRange(hsv, lower, upper)

                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                clicked = False
                for contour in contours:
                    if not self.running.is_set():
                        return
                    area = cv2.contourArea(contour)
                    if area > 300:
                        bx, by, bw, bh = cv2.boundingRect(contour)
                        click_x = bx + bw // 2 + region_offset_x
                        click_y = by + bh // 2 + region_offset_y
                        pyautogui.moveTo(click_x, click_y)
                        pyautogui.click(button=self._click_button)
                        clicked = True

                        if self._use_repeat_count:
                            self.click_count -= 1
                            if self.click_count <= 0:
                                self.running.clear()
                                self.signals.update_status.emit('✅ Tamamlandı')
                                return
                            self.signals.update_status.emit(
                                f'🟢 Tıklandı — Kalan: {self.click_count}'
                            )
                        break

                if not clicked:
                    self.signals.update_status.emit(
                        f'🔍 Renk aranıyor... (gecikme: {self.delay:.2f}s)'
                    )

                time.sleep(self.delay)

        except pyautogui.FailSafeException:
            self.signals.show_warning.emit(
                'Durduruldu',
                'PyAutoGUI fail-safe etkinleştirildi.\n'
                'Fareyi ekranın köşesine götürerek durdurdunuz.'
            )
            self.running.clear()
            self.signals.update_status.emit('⚠ Fail-safe ile durduruldu')
        except Exception as e:
            self.signals.show_warning.emit('Hata', f'Tıklama sırasında hata: {e}')
            self.running.clear()
            self.signals.update_status.emit('❌ Hata ile durduruldu')
        finally:
            # Başlat butonunu tekrar aktif et (thread-safe)
            QtCore.QMetaObject.invokeMethod(
                self.start_button, "setEnabled",
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(bool, True)
            )

    def closeEvent(self, event):
        self.running.clear()
        keyboard.unhook_all()
        event.accept()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')

    # Koyu tema
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(45, 45, 48))
    palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(230, 230, 230))
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(30, 30, 30))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(45, 45, 48))
    palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(230, 230, 230))
    palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(230, 230, 230))
    palette.setColor(QtGui.QPalette.Text, QtGui.QColor(230, 230, 230))
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(55, 55, 58))
    palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(230, 230, 230))
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(76, 175, 80))
    palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(0, 0, 0))
    app.setPalette(palette)

    window = AutoClickerGUI()
    sys.exit(app.exec_())

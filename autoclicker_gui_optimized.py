import sys
import cv2
import numpy as np
import pyautogui
import mss
from PIL import Image
import time
import json
import os
from datetime import datetime
from PyQt5 import QtWidgets, QtCore, QtGui
import threading
import keyboard
import ctypes
from ctypes import wintypes
from collections import deque
import random


class PerformanceMetrics:
    """Track clicks per second, latency, and other metrics."""
    def __init__(self, window_size=60):
        self.window_size = window_size
        self.click_times = deque(maxlen=window_size)
        self.total_clicks = 0
        self.start_time = None
        self.lock = threading.Lock()

    def record_click(self):
        with self.lock:
            self.click_times.append(time.perf_counter())
            self.total_clicks += 1
            if self.start_time is None:
                self.start_time = self.click_times[0]

    def get_cps(self):
        """Get current clicks per second."""
        with self.lock:
            if len(self.click_times) < 2:
                return 0.0
            time_span = self.click_times[-1] - self.click_times[0]
            return len(self.click_times) / time_span if time_span > 0 else 0.0

    def get_average_cps(self):
        """Get average clicks per second since start."""
        with self.lock:
            if self.start_time is None or self.total_clicks < 1:
                return 0.0
            elapsed = time.perf_counter() - self.start_time
            return self.total_clicks / elapsed if elapsed > 0 else 0.0


class StatusSignal(QtCore.QObject):
    """Thread-safe signal for updating GUI from background threads."""
    update_status = QtCore.pyqtSignal(str)
    show_warning = QtCore.pyqtSignal(str, str)
    request_start = QtCore.pyqtSignal()
    request_stop = QtCore.pyqtSignal()


class ConfigManager:
    """Save and load configuration profiles."""
    def __init__(self, config_dir="./profiles"):
        self.config_dir = config_dir
        os.makedirs(config_dir, exist_ok=True)

    def save_config(self, name, config):
        """Save configuration profile."""
        try:
            filepath = os.path.join(self.config_dir, f"{name}.json")
            with open(filepath, 'w') as f:
                json.dump(config, f, indent=2)
            return True, f"Profil kaydedildi: {name}"
        except Exception as e:
            return False, str(e)

    def load_config(self, name):
        """Load configuration profile."""
        try:
            filepath = os.path.join(self.config_dir, f"{name}.json")
            with open(filepath, 'r') as f:
                return True, json.load(f)
        except Exception as e:
            return False, str(e)

    def list_configs(self):
        """List all saved profiles."""
        try:
            files = [f[:-5] for f in os.listdir(self.config_dir) if f.endswith('.json')]
            return files
        except:
            return []


class AutoClickerGUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        # Speed up pyautogui actions
        try:
            pyautogui.PAUSE = 0
        except Exception:
            pass
        
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
        
        # Performance settings
        self.performance_mode = False
        self.scale_factor = 1.0
        self.contour_min_area = 300
        self.benchmark_count = 1000
        
        # Optimization settings
        self.use_morphology = True
        self.morphology_kernel_size = 3
        self.enable_jitter = False
        self.jitter_amount = 2  # pixels
        self.max_click_rate = 0  # 0 = unlimited
        
        # Metrics
        self.metrics = PerformanceMetrics()
        self.config_manager = ConfigManager()
        
        # Thread-safe snapshots at start
        self._use_color = False
        self._use_repeat_count = False
        self._click_button = 'left'
        self._use_region = False
        
        # Screenshot caching
        self._last_screenshot = None
        self._screenshot_time = 0
        
        self.initUI()
        self._register_hotkeys()

    def initUI(self):
        self.setWindowTitle('Auto Clicker Pro — Optimized & Professional')
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(540)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setSpacing(10)

        # --- Delay Settings ---
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

        # --- Click Settings ---
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

        # --- Color Settings ---
        color_group = QtWidgets.QGroupBox('🎨 Renk Algılama (opsiyonel)')
        color_layout = QtWidgets.QHBoxLayout()
        self.color_input = QtWidgets.QLineEdit()
        self.color_input.setPlaceholderText('Örn: 40,40,40 - 80,255,255')
        self.color_pick_button = QtWidgets.QPushButton('🔍 Renk Seç')
        self.color_pick_button.clicked.connect(self.pick_color)
        color_layout.addWidget(self.color_input, stretch=1)
        color_layout.addWidget(self.color_pick_button)
        color_group.setLayout(color_layout)
        main_layout.addWidget(color_group)

        # --- Performance Mode ---
        perf_group = QtWidgets.QGroupBox('⚡ Performans Optimizasyonu')
        perf_layout = QtWidgets.QVBoxLayout()
        
        perf_row1 = QtWidgets.QHBoxLayout()
        self.perf_checkbox = QtWidgets.QCheckBox('Performans Modu')
        self.perf_checkbox.stateChanged.connect(self.toggle_performance_mode)
        self.scale_combo = QtWidgets.QComboBox()
        self.scale_combo.addItems(['1.0','0.75','0.5','0.25'])
        self.scale_combo.setCurrentIndex(2)
        self.scale_combo.setDisabled(True)
        perf_row1.addWidget(self.perf_checkbox)
        perf_row1.addWidget(QtWidgets.QLabel('Ölçek:'))
        perf_row1.addWidget(self.scale_combo)
        perf_row1.addWidget(QtWidgets.QLabel('Min Alan:'))
        self.area_spin = QtWidgets.QSpinBox()
        self.area_spin.setRange(1, 100000)
        self.area_spin.setValue(300)
        perf_row1.addWidget(self.area_spin)
        perf_layout.addLayout(perf_row1)
        
        # Morphology & Jitter
        perf_row2 = QtWidgets.QHBoxLayout()
        self.morph_checkbox = QtWidgets.QCheckBox('Morfoloji (Denoise)')
        self.morph_checkbox.setChecked(True)
        self.jitter_checkbox = QtWidgets.QCheckBox('Jitter (Anti-Detection)')
        self.jitter_checkbox.stateChanged.connect(self.toggle_jitter)
        self.jitter_spin = QtWidgets.QSpinBox()
        self.jitter_spin.setRange(1, 20)
        self.jitter_spin.setValue(2)
        self.jitter_spin.setSuffix(' px')
        self.jitter_spin.setDisabled(True)
        perf_row2.addWidget(self.morph_checkbox)
        perf_row2.addWidget(self.jitter_checkbox)
        perf_row2.addWidget(QtWidgets.QLabel('Jitter:'))
        perf_row2.addWidget(self.jitter_spin)
        perf_layout.addLayout(perf_row2)
        
        perf_group.setLayout(perf_layout)
        main_layout.addWidget(perf_group)

        # --- Region Selection ---
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

        # --- Profiles ---
        profile_group = QtWidgets.QGroupBox('💾 Profil Yönetimi')
        profile_layout = QtWidgets.QHBoxLayout()
        self.profile_combo = QtWidgets.QComboBox()
        self.profile_combo.addItem('(Yeni Profil)')
        self.profile_combo.addItems(self.config_manager.list_configs())
        self.profile_name_input = QtWidgets.QLineEdit()
        self.profile_name_input.setPlaceholderText('Profil adı...')
        self.save_profile_button = QtWidgets.QPushButton('💾 Kaydet')
        self.save_profile_button.clicked.connect(self.save_profile)
        self.load_profile_button = QtWidgets.QPushButton('📂 Yükle')
        self.load_profile_button.clicked.connect(self.load_profile)
        profile_layout.addWidget(self.profile_combo)
        profile_layout.addWidget(self.profile_name_input)
        profile_layout.addWidget(self.save_profile_button)
        profile_layout.addWidget(self.load_profile_button)
        profile_group.setLayout(profile_layout)
        main_layout.addWidget(profile_group)

        # --- Control Buttons ---
        control_layout = QtWidgets.QHBoxLayout()
        self.benchmark_count_input = QtWidgets.QSpinBox()
        self.benchmark_count_input.setRange(10, 2000000)
        self.benchmark_count_input.setValue(1000)
        self.benchmark_button = QtWidgets.QPushButton('📊 Benchmark')
        self.benchmark_button.clicked.connect(self.start_benchmark)
        control_layout.addWidget(self.benchmark_button)
        control_layout.addWidget(QtWidgets.QLabel('Clicks:'))
        control_layout.addWidget(self.benchmark_count_input)
        
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

        # --- Status Bar with Metrics ---
        self.status_label = QtWidgets.QLabel('⏸ Durum: Bekleniyor')
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setStyleSheet(
            'font-size: 12px; padding: 8px; background-color: #333;'
            'color: #eee; border-radius: 4px;'
        )
        
        self.metrics_label = QtWidgets.QLabel('CPS: 0.00 | Toplam: 0')
        self.metrics_label.setAlignment(QtCore.Qt.AlignCenter)
        self.metrics_label.setStyleSheet(
            'font-size: 11px; padding: 4px; background-color: #222;'
            'color: #aaa; border-radius: 4px;'
        )
        
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(self.metrics_label)

        self.setLayout(main_layout)
        
        # Metrics update timer
        self.metrics_timer = QtCore.QTimer()
        self.metrics_timer.timeout.connect(self._update_metrics_display)
        self.metrics_timer.start(500)  # Update every 500ms

        QtWidgets.QShortcut(QtGui.QKeySequence('F6'), self).activated.connect(self.start_clicker)
        QtWidgets.QShortcut(QtGui.QKeySequence('F7'), self).activated.connect(self.stop_clicker)

        self.show()

    def _register_hotkeys(self):
        keyboard.add_hotkey('f6', lambda: self.signals.request_start.emit())
        keyboard.add_hotkey('f7', lambda: self.signals.request_stop.emit())

    @QtCore.pyqtSlot(str)
    def _update_status_label(self, text):
        self.status_label.setText(text)

    @QtCore.pyqtSlot(str, str)
    def _show_warning(self, title, message):
        QtWidgets.QMessageBox.warning(self, title, message)

    def _update_metrics_display(self):
        cps = self.metrics.get_cps()
        avg_cps = self.metrics.get_average_cps()
        self.metrics_label.setText(
            f'CPS: {cps:.2f} | Ort: {avg_cps:.2f} | Toplam: {self.metrics.total_clicks}'
        )

    def toggle_click_count_input(self):
        self.click_count_input.setDisabled(not self.click_repeat_once.isChecked())

    def toggle_region_selection(self, state):
        self.region_select_button.setDisabled(state == QtCore.Qt.Unchecked)

    def toggle_performance_mode(self, state):
        enabled = state == QtCore.Qt.Checked
        self.scale_combo.setDisabled(not enabled)
        self.area_spin.setDisabled(not enabled)

    def toggle_jitter(self, state):
        enabled = state == QtCore.Qt.Checked
        self.jitter_spin.setDisabled(not enabled)

    def save_profile(self):
        name = self.profile_name_input.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, 'Hata', 'Profil adı girin.')
            return
        
        config = {
            'delay_seconds': self.delay_seconds_input.value(),
            'delay_milliseconds': self.delay_milliseconds_input.value(),
            'click_type': self.click_option.currentText(),
            'repeat_mode': 'once' if self.click_repeat_once.isChecked() else 'until_stop',
            'click_count': self.click_count_input.value(),
            'color_range': self.color_input.text(),
            'performance_mode': self.perf_checkbox.isChecked(),
            'scale_factor': self.scale_combo.currentText(),
            'morphology': self.morph_checkbox.isChecked(),
            'jitter': self.jitter_checkbox.isChecked(),
            'jitter_amount': self.jitter_spin.value(),
            'region_selection': self.region_checkbox.isChecked(),
        }
        
        success, msg = self.config_manager.save_config(name, config)
        QtWidgets.QMessageBox.information(self, 'Başarılı' if success else 'Hata', msg)
        
        if success:
            # Refresh combo
            self.profile_combo.clear()
            self.profile_combo.addItem('(Yeni Profil)')
            self.profile_combo.addItems(self.config_manager.list_configs())
            self.profile_name_input.clear()

    def load_profile(self):
        name = self.profile_combo.currentText()
        if name == '(Yeni Profil)':
            return
        
        success, config = self.config_manager.load_config(name)
        if not success:
            QtWidgets.QMessageBox.warning(self, 'Hata', f'Profil yüklenemedi: {config}')
            return
        
        # Apply settings
        self.delay_seconds_input.setValue(config.get('delay_seconds', 0))
        self.delay_milliseconds_input.setValue(config.get('delay_milliseconds', 100))
        idx = self.click_option.findText(config.get('click_type', 'Sol Tık'))
        if idx >= 0:
            self.click_option.setCurrentIndex(idx)
        
        is_once = config.get('repeat_mode') == 'once'
        self.click_repeat_once.setChecked(is_once)
        self.click_repeat_until_stopped.setChecked(not is_once)
        self.click_count_input.setValue(config.get('click_count', 10))
        self.color_input.setText(config.get('color_range', ''))
        self.perf_checkbox.setChecked(config.get('performance_mode', False))
        
        idx = self.scale_combo.findText(config.get('scale_factor', '0.5'))
        if idx >= 0:
            self.scale_combo.setCurrentIndex(idx)
        
        self.morph_checkbox.setChecked(config.get('morphology', True))
        self.jitter_checkbox.setChecked(config.get('jitter', False))
        self.jitter_spin.setValue(config.get('jitter_amount', 2))
        
        QtWidgets.QMessageBox.information(self, 'Başarılı', f'Profil yüklendi: {name}')

    def start_clicker(self):
        if self.running.is_set():
            return

        try:
            seconds = self.delay_seconds_input.value()
            milliseconds = self.delay_milliseconds_input.value()
            self.delay = seconds + (milliseconds / 1000.0)
            if self.delay < 0.001:
                self.delay = 0.001

            color_text = self.color_input.text().strip()
            if color_text:
                self.color_range = self.parse_color_input(color_text)
                if not self.color_range:
                    raise ValueError("Renk aralığı formatı hatalı.\nÖrnek: 40,40,40 - 80,255,255")
                self._use_color = True
            else:
                self.color_range = None
                self._use_color = False

            self._use_repeat_count = self.click_repeat_once.isChecked()
            self._click_button = 'left' if self.click_option.currentText() == 'Sol Tık' else 'right'
            self._use_region = self.region_checkbox.isChecked()
            
            self.performance_mode = self.perf_checkbox.isChecked()
            try:
                self.scale_factor = float(self.scale_combo.currentText())
            except Exception:
                self.scale_factor = 1.0
            
            self.contour_min_area = int(self.area_spin.value())
            self.use_morphology = self.morph_checkbox.isChecked()
            self.enable_jitter = self.jitter_checkbox.isChecked()
            self.jitter_amount = self.jitter_spin.value()

            if self._use_repeat_count:
                self.click_count = self.click_count_input.value()
                if self.click_count <= 0:
                    raise ValueError("Tıklama sayısı en az 1 olmalı.")

            if self._use_region and self.region_coords is None:
                raise ValueError('Önce bir bölge seçmelisiniz.')

            # Reset metrics
            self.metrics = PerformanceMetrics()
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

    def pick_color(self):
        threading.Thread(target=self._pick_color_worker, daemon=True).start()

    def start_benchmark(self):
        if self.running.is_set():
            QtWidgets.QMessageBox.warning(self, 'Uyarı', 'Önce çalışan işlemi durdurun.')
            return
        count = int(self.benchmark_count_input.value())
        reply = QtWidgets.QMessageBox.question(
            self, 'Benchmark Onayı',
            f'{count} tıklama yapılacak — devam edilsin mi?\n(Yoğun tıklama oluşturacaktır)'
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return
        threading.Thread(target=self._benchmark_worker, args=(count,), daemon=True).start()

    def _benchmark_worker(self, count):
        try:
            QtCore.QMetaObject.invokeMethod(
                self.start_button, "setEnabled",
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(bool, False)
            )
            self.signals.update_status.emit('⚡ Benchmark: Başlıyor')
            self.metrics = PerformanceMetrics()
            
            t0 = time.perf_counter()
            for i in range(count):
                try:
                    self._send_mouse_click(button=self._click_button)
                    self.metrics.record_click()
                except Exception:
                    pyautogui.click(button=self._click_button)
                    self.metrics.record_click()
            t1 = time.perf_counter()
            
            elapsed = t1 - t0
            cps = count / elapsed if elapsed > 0 else float('inf')
            QtWidgets.QMessageBox.information(
                self, 'Benchmark Sonucu',
                f'Click/s: {cps:.2f}\nSüre: {elapsed:.3f}s\nToplam: {count}'
            )
            self.signals.update_status.emit('✅ Benchmark tamamlandı')
        except Exception as e:
            self.signals.show_warning.emit('Hata', f'Benchmark hatası: {e}')
        finally:
            QtCore.QMetaObject.invokeMethod(
                self.start_button, "setEnabled",
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(bool, True)
            )

    def _pick_color_worker(self):
        try:
            screenshot = self._get_screenshot()
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
                    self.signals.update_status.emit(f'🎨 Renk seçildi: {result}')
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
                if key == 27:
                    break
            cv2.destroyAllWindows()
        except Exception as e:
            self.signals.show_warning.emit('Hata', f'Renk seçimi hatası: {e}')

    def _get_screenshot(self, region=None):
        """Return RGB numpy array — optimized for speed."""
        try:
            img = pyautogui.screenshot(region=region)
            arr = np.array(img)
            return arr
        except Exception:
            try:
                with mss.mss() as sct:
                    if region:
                        x, y, w, h = region
                        monitor = {"left": int(x), "top": int(y), "width": int(w), "height": int(h)}
                        sct_img = sct.grab(monitor)
                    else:
                        sct_img = sct.grab(sct.monitors[0])
                    arr = np.array(sct_img)
                    if arr.shape[2] == 4:
                        arr = arr[..., :3]
                    arr = arr[..., ::-1]
                    return arr
            except Exception as e:
                raise RuntimeError(f'Ekran yakalama hatası: {e}')

    def _set_cursor_pos(self, x, y):
        ctypes.windll.user32.SetCursorPos(int(x), int(y))

    def _send_mouse_click(self, button='left'):
        """Send mouse click via Windows SendInput — ultra-fast."""
        INPUT_MOUSE = 0
        class MOUSEINPUT(ctypes.Structure):
            _fields_ = (('dx', wintypes.LONG), ('dy', wintypes.LONG), ('mouseData', wintypes.DWORD),
                        ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', wintypes.ULONG_PTR))

        class INPUT(ctypes.Structure):
            class _I(ctypes.Union):
                _fields_ = (('mi', MOUSEINPUT),)
            _fields_ = (('type', wintypes.DWORD), ('ii', _I))

        if button == 'left':
            down = 0x0002
            up = 0x0004
        else:
            down = 0x0008
            up = 0x0010

        inp_down = INPUT()
        inp_down.type = INPUT_MOUSE
        inp_down.ii.mi = MOUSEINPUT(0, 0, 0, down, 0, 0)

        inp_up = INPUT()
        inp_up.type = INPUT_MOUSE
        inp_up.ii.mi = MOUSEINPUT(0, 0, 0, up, 0, 0)

        ctypes.windll.user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(inp_down))
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(inp_up))

    def _send_click_at(self, x, y, button='left'):
        """Move to position and click."""
        if self.enable_jitter:
            # Add random jitter to avoid detection
            jx = x + random.randint(-self.jitter_amount, self.jitter_amount)
            jy = y + random.randint(-self.jitter_amount, self.jitter_amount)
            self._set_cursor_pos(jx, jy)
        else:
            self._set_cursor_pos(x, y)
        self._send_mouse_click(button=button)

    def _smart_sleep(self, duration):
        """Sleep with high precision and minimal CPU usage."""
        end = time.perf_counter() + duration
        while time.perf_counter() < end:
            if not self.running.is_set():
                break
            remaining = end - time.perf_counter()
            if remaining > 0.001:
                time.sleep(min(0.0001, remaining / 10))
            else:
                time.sleep(0)

    def select_region(self):
        threading.Thread(target=self._select_region_worker, daemon=True).start()

    def _select_region_worker(self):
        try:
            screenshot = self._get_screenshot()
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

    def auto_clicker(self):
        """Main clicking loop — optimized."""
        try:
            while self.running.is_set():
                if not self._use_color:
                    # Simple position-based clicking
                    try:
                        self._send_mouse_click(button=self._click_button)
                        self.metrics.record_click()
                    except Exception:
                        pyautogui.click(button=self._click_button)
                        self.metrics.record_click()

                    if self._use_repeat_count:
                        self.click_count -= 1
                        if self.click_count <= 0:
                            self.running.clear()
                            self.signals.update_status.emit('✅ Tamamlandı')
                            break
                        self.signals.update_status.emit(
                            f'🟢 Tıklandı — Kalan: {self.click_count}'
                        )
                    
                    self._smart_sleep(self.delay)
                    continue

                # Color-based detection
                region_offset_x = 0
                region_offset_y = 0

                if self._use_region and self.region_coords is not None:
                    rx, ry, rw, rh = self.region_coords
                    screenshot = self._get_screenshot(region=(rx, ry, rw, rh))
                    region_offset_x, region_offset_y = rx, ry
                else:
                    screenshot = self._get_screenshot()

                frame = np.array(screenshot)

                # Performance scaling
                scale = self.scale_factor if self.performance_mode else 1.0
                if scale != 1.0:
                    small = cv2.resize(frame, dsize=(0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
                else:
                    small = frame

                hsv = cv2.cvtColor(small, cv2.COLOR_RGB2HSV)

                lower, upper = self.color_range
                mask = cv2.inRange(hsv, lower, upper)

                # Morphological operations for denoising
                if self.use_morphology:
                    kernel_size = self.morphology_kernel_size
                    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)  # Remove noise
                    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)  # Fill gaps

                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                clicked = False
                for contour in contours:
                    if not self.running.is_set():
                        return
                    area = cv2.contourArea(contour)
                    thresh = int(self.contour_min_area * (scale * scale))
                    if area > thresh:
                        bx, by, bw, bh = cv2.boundingRect(contour)
                        if scale != 1.0:
                            click_x = int((bx + bw // 2) / scale) + region_offset_x
                            click_y = int((by + bh // 2) / scale) + region_offset_y
                        else:
                            click_x = bx + bw // 2 + region_offset_x
                            click_y = by + bh // 2 + region_offset_y
                        try:
                            self._send_click_at(click_x, click_y, button=self._click_button)
                            self.metrics.record_click()
                        except Exception:
                            pyautogui.moveTo(click_x, click_y)
                            pyautogui.click(button=self._click_button)
                            self.metrics.record_click()
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

                self._smart_sleep(self.delay)

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
            QtCore.QMetaObject.invokeMethod(
                self.start_button, "setEnabled",
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(bool, True)
            )

    def closeEvent(self, event):
        self.running.clear()
        self.metrics_timer.stop()
        keyboard.unhook_all()
        event.accept()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')

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

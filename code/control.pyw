import serial
import time
import sys
import os
import glob
import csv
import multiprocessing as mp
import numpy as np
from pathlib import Path

from PyQt5.QtCore import QObject, QSize, Qt, QTimer, QEventLoop, pyqtSignal, QCoreApplication, QThread, pyqtSlot
from PyQt5.QtGui import QPalette, QColor, QFont, QIntValidator, QKeyEvent, QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDial,
    QDoubleSpinBox,
    QFontComboBox,
    QLabel,
    QLCDNumber,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
    QTabWidget,
    QHBoxLayout,
    QGridLayout,
    QTextEdit, 
    QStackedWidget,
    QFileDialog,
    QSizePolicy
)

from PIL import Image

# Add Windows-specific imports for dark title bar
import ctypes
from ctypes import wintypes

# Add reference to the C# SDK DLL
import clr
clr.AddReference(r"CameraSdkCs")
clr.AddReference(r"ImageSdkCs")
from P1.CameraSdk import Camera
from P1.ImageSdk import *
import System

STAGE_STEPS_PER_REVOLUTION = 0
TRACK_MAX_STEPS = 0
NOD_MAX_STEPS = 0

class LiveViewWorker(QObject):

    live_view_frame_ready = pyqtSignal(QImage)

    def __init__(self, camera):
        super().__init__(None)
        self.running = False
        self.camera = camera

    @pyqtSlot()
    def start(self):
        self.running = True
        while self.running:
            frame = self.camera.WaitForLiveView(1000)
            data = frame.Data.ToArray()
            image = QImage(bytes(data), frame.Width, frame.Height, QImage.Format_RGB888)
            self.live_view_frame_ready.emit(image)
    
    @pyqtSlot()
    def stop(self):
        self.running = False


class LiveViewViewer(QLabel):
    def __init__(self, placeholder_text):
        super().__init__(placeholder_text)
    
    @pyqtSlot(QImage)
    def on_frame(self, image):
        pixmap = QPixmap.fromImage(image)
        self.setPixmap(pixmap)
    

class ControlUI(QMainWindow):

    user_txt_input = pyqtSignal(str)
    all_motors_stopped = pyqtSignal()

    YELLOW_PROGRESS_COLOR = "#cd9c5c"

    pos_line_edit_matched_style = """
        QLineEdit {
            background-color: #3a3a3a;
        }"""
    pos_line_edit_unmatched_style = f"""
        QLineEdit {{
            background-color: {YELLOW_PROGRESS_COLOR};
        }}"""
    
    standard_button_style = """
        QPushButton {
            background-color: #3a3a3a;
            border: none;
            border-radius: 8px;
            padding: 4px 8px;
            font-size: 9pt;
        }
        QPushButton:hover {
            background-color: #4a4a4a;
        }
        QPushButton:pressed {
            background-color: #2a2a2a;
        }
    """
    standard_button_style_long = """
        QPushButton {
            background-color: #3a3a3a;
            border-radius: 8px;
            padding: 4px 8px;
            font-size: 12pt;
            font-weight: bold;
            margin: 10px;
        }
        QPushButton:hover {
            background-color: #4a4a4a;
        }
        QPushButton:pressed {
            background-color: #2a2a2a;
        }
    """
    standard_button_style_long_in_progress = f"""
        QPushButton {{
            background-color: {YELLOW_PROGRESS_COLOR};
            border-radius: 8px;
            padding: 4px 8px;
            font-size: 12pt;
            font-weight: bold;
            margin: 10px;
        }}
    """

    standard_checkbox_style = """
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            background-color: #3a3a3a;
            border: none;
            border-radius: 3px;
        }
        QCheckBox::indicator:checked {
            background-color: #5ccd80;
        }
        QCheckBox::indicator:checked:hover {
            background-color: #6cdd90;
        }
        QCheckBox::indicator:hover {
            background-color: #4a4a4a;
        }
    """
    standard_label_font = """
        /*font-size: 9pt; */
    """

    big_button_style_red = f"""
        QPushButton {{
                background-color: #cd5c5c;
                color: #FFFFFF;
                border: 2px solid #DC6C6C;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 12pt;
                font-weight: bold;
                margin: 10px;
            }}
            QPushButton:hover {{
                background-color: #DC6C6C;
                border: 2px solid #EC7C7C;
            }}
            QPushButton:pressed {{
                background-color: #BC4C4C;
                border: 2px solid #CC5C5C;
            }}
    """

    small_line_edit_style = """
                QLineEdit {
                    background-color: #3a3a3a;
                    font-size: 10pt;
                }
            """

    default_capture_directory = os.path.dirname(os.getcwd()) + "/captures/default"

    def __init__(self):
        super().__init__()

        self.update_positions = [True, True, True]
        self.motor_data = [{ "is_running": None, "position": None, "speed": None, "accel": None } for axis in range(3)]
        self.homing = [False, False, False]
        self.wrong_direction_flag = False
        self.alarm_flag = False
        self.needs_homing_flag = False
        self.microcontroller_connected = False
        self.actively_editing_position = [False, False, False, False]
        self.estop_pressed = False
        self.cancel_sequence_flag = False
        self.calibration_in_progress = mp.Event()
        self.waiting_for_input = False
        self.last_command = None
        self.spin_rows = []
        self.spin_cols = []
        self.capture_directory = self.default_capture_directory
        self.camera = None
        self.live_view_worker = None
        self.live_view_thread = None

        self.setWindowTitle("lbxcontrol")
        self.setGeometry(400, 100, 1800, 900)
        self.set_dark_theme()
        self.set_dark_title_bar()  # Add dark title bar
        self.init_ui()
        self.initialize_hardware()
        self.setup_serial_polling()
        
        # Setup keyboard handling
        self.pressed_keys = set()
        self.keyboard_timer = QTimer()
        self.keyboard_timer.timeout.connect(self.process_keyboard_commands)
        self.keyboard_timer.start(1000)  # Fire every 1000ms

    def set_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(20, 20, 20))
        palette.setColor(QPalette.AlternateBase, QColor(35, 35, 35))
        palette.setColor(QPalette.ToolTipBase, Qt.white)
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(40, 40, 40))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(100, 149, 237))
        palette.setColor(QPalette.Highlight, QColor(100, 149, 237))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        QApplication.instance().setPalette(palette)
    
    def set_dark_title_bar(self):
        """Set dark title bar on Windows"""
        if sys.platform == "win32":
            hwnd = int(self.winId())
            # Use Windows API to enable dark title bar with custom color
            # First enable dark mode
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 20, ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int)
            )
            # Set title bar color to match terminal background (#181818)
            color = 0x00181818  # BGR format: 0x00BBGGRR
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 35, ctypes.byref(ctypes.c_int(color)), ctypes.sizeof(ctypes.c_int)
            )

    def init_ui(self):
        ## Define UI sections
        self.machine_controls = QWidget()
        self.capture_sequence = QWidget()
        self.calibrate = QWidget()
        self.live_view = LiveViewViewer(" ")
        self.last_image = QLabel(" ")

        ## Set overall layout of the UI sections
        left_tabs = QTabWidget()
        left_tabs.setTabPosition(QTabWidget.North)
        # left_tabs.setFixedWidth(500)
        left_tabs.setStyleSheet("""
            QTabWidget::pane { 
                background-color: #252525;
                border-top-left-radius: 0px;
            }
            QTabBar::tab:selected {
                background: #252525;
            }
        """)
        left_tabs.addTab(self.machine_controls, "Manual Controls")

        center_tabs = QTabWidget()
        center_tabs.setStyleSheet(left_tabs.styleSheet())
        center_tabs.setTabPosition(QTabWidget.North)
        center_tabs.addTab(self.last_image, "Latest Captured Image")
        center_tabs.addTab(self.live_view, "Live View")
        center_tabs.currentChanged.connect(self.on_tab_changed)

        right_tabs = QTabWidget()
        right_tabs.setStyleSheet(left_tabs.styleSheet())
        right_tabs.setTabPosition(QTabWidget.North)
        right_tabs.setMinimumWidth(500)
        right_tabs.addTab(self.capture_sequence, "Capture Sequence")

        top_row = QWidget()
        top_layout = QHBoxLayout()
        top_layout.addWidget(left_tabs)
        top_layout.addWidget(center_tabs, 1)
        top_layout.addWidget(right_tabs)
        top_row.setLayout(top_layout)

        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setFixedHeight(120)  # Approximately 6 lines
        self.terminal_output.setStyleSheet("""
            background-color: #181818; 
            color: #FFFFFF; 
            font-family: 'Consolas'; 
            font-size: 14px; 
            margin-right: 13px;
            margin-left: 13px;
        """)

        # Add command input field
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Enter command...")
        self.command_input.setStyleSheet("""
            background-color: #181818; 
            color: #FFFFFF; 
            font-family: 'Consolas'; 
            font-size: 14px; 
            margin-right: 13px;
            margin-left: 13px;
        """)
        self.command_input.returnPressed.connect(self.process_command_input)

        root_layout = QVBoxLayout()
        root_layout.addWidget(top_row)
        root_layout.addWidget(self.terminal_output)
        root_layout.addWidget(self.command_input)
        root_widget = QWidget()
        root_widget.setLayout(root_layout)
        self.setCentralWidget(root_widget)

        tab_font = left_tabs.font()
#region
#region

        ### Populate "Machine Controls" tab ###
        machine_controls_layout = QVBoxLayout(self.machine_controls)

        self.geo_grid = QWidget()
        geo_grid_layout = QGridLayout(self.geo_grid)

        self.geo = [{}, {}, {}, {}]
        for axis, axis_name in enumerate(["θ", "φ", "h", "f"]):
            axis_label = QLabel(axis_name + " ")
            axis_main_font_style = """
                font-size: 12pt;
            """
            axis_label.setStyleSheet(axis_main_font_style)
            geo_grid_layout.addWidget(axis_label, axis * 4, 0)

            pos_line_edit = QLineEdit()
            # pos_line_edit.editingFinished.connect(lambda checked=False, a=axis: self.new_position_entered(a))
            pos_line_edit.returnPressed.connect(lambda le=pos_line_edit: le.clearFocus())
            pos_line_edit.focusInEvent = lambda event, a=axis, le=pos_line_edit: self.position_focus_in(event, a, le)
            pos_line_edit.focusOutEvent = lambda event, a=axis, le=pos_line_edit: self.position_focus_out(event, a, le)
            pos_line_edit.setStyleSheet(self.pos_line_edit_matched_style)
            self.geo[axis]['pos_line_edit'] = pos_line_edit
            geo_grid_layout.addWidget(pos_line_edit, axis * 4, 1, 1, 3)

            units = "(°)" if axis < 2 else "(mm)"
            unit_label = QLabel(units)
            unit_label.setStyleSheet(axis_main_font_style)
            geo_grid_layout.addWidget(unit_label, axis * 4, 4)
            
            slider_style = """
                QSlider::groove:horizontal {
                    height: 6px;
                    background: #3a3a3a;
                }
                QSlider::handle:horizontal {
                    background: #666;
                    width: 12px;
                    margin: -3px 0;
                }
                QSlider::handle:horizontal:hover {
                    background: #777;
                }
            """

            axis_sub_font_style = "font-size: 9pt;"

            if axis < 3:
                for j, rate_type in enumerate(["speed", "accel"]):
                    row = axis * 4 + 1 + j

                    # Add rate labels
                    rate_label = QLabel(rate_type + ":")
                    rate_label.setStyleSheet(axis_sub_font_style)
                    geo_grid_layout.addWidget(rate_label, row, 1)

                    # Add rate slider
                    rate_slider = QSlider(Qt.Horizontal)
                    rate_slider.setRange(1, 100)
                    rate_slider.setValue(50)
                    rate_slider.setMaximumWidth(100)
                    rate_slider.setStyleSheet(slider_style)
                    self.geo[axis][rate_type + '_slider'] = rate_slider
                    geo_grid_layout.addWidget(rate_slider, row, 2)

                    # Add rate text field
                    rate_line_edit = QLineEdit()
                    rate_line_edit.setText("50")
                    rate_line_edit.setMaximumWidth(60)
                    rate_validator = QIntValidator(0, 999)
                    rate_line_edit.setValidator(rate_validator)
                    rate_line_edit.setStyleSheet(self.small_line_edit_style)
                    self.geo[axis][rate_type + '_line_edit'] = rate_line_edit
                    geo_grid_layout.addWidget(rate_line_edit, row, 3)

                    # Connect rate slider and text field
                    rate_line_edit.returnPressed.connect(lambda le=rate_line_edit: le.clearFocus())
                    rate_line_edit.focusOutEvent = lambda event, r=rate_type, a=axis, le=rate_line_edit, s=rate_slider: self.rate_line_edit_focus_out(event, r, a, le, s)
                    rate_slider.valueChanged.connect(lambda value, line_edit=rate_line_edit: line_edit.setText(str(value)))
                    rate_slider.sliderReleased.connect(lambda r=rate_type, a=axis: self.new_rate_entered(r, a))

                    # Add percent label for rate
                    rate_percent_label = QLabel("%")
                    rate_percent_label.setStyleSheet(axis_sub_font_style)
                    geo_grid_layout.addWidget(rate_percent_label, row, 4)

                    # Add spacing row after each axis
                    geo_grid_layout.setRowMinimumHeight(axis * 4 + 3, 20)
                    geo_grid_layout.setRowStretch(axis * 4 + 3, 0)

        geo_grid_layout.setColumnStretch(5, 1)

        machine_controls_layout.addWidget(self.geo_grid)
        
        # Add stop button
        stop_button = QPushButton("STOP")
        stop_button.setFixedHeight(70)
        stop_button.setStyleSheet(self.big_button_style_red)
        stop_button.clicked.connect(self.stop_all_motors)
        machine_controls_layout.addWidget(stop_button)

        # Keyboard controls
        self.keyboard_controls_widget = QWidget()
        machine_controls_layout.addWidget(self.keyboard_controls_widget)
        keyboard_controls_layout = QHBoxLayout(self.keyboard_controls_widget)
        keyboard_controls_layout.setContentsMargins(10, 5, 10, 5)

        keyboard_controls_label = QLabel("Enable keyboard controls")
        keyboard_controls_layout.addWidget(keyboard_controls_label)
        keyboard_controls_label.setStyleSheet(self.standard_label_font)

        # Add help button
        help_button = QPushButton("?")
        keyboard_controls_layout.addWidget(help_button)
        help_button.setFixedSize(24, 24)
        help_button.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                border: none;
                border-radius: 12px;
                font-size: 7pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        help_button.setToolTip(
            "Keyboard Controls:<br>"
            "<table style='border-collapse:collapse;'>"
            "<tr><td style='padding-right:16px; text-align:right;'>A/D:</td><td>θ ±</td></tr>"
            "<tr><td style='padding-right:16px; text-align:right;'>W/S:</td><td>φ ±</td></tr>"
            "<tr><td style='padding-right:16px; text-align:right;'>E/Q:</td><td>h ±</td></tr>"
            "<tr><td style='padding-right:16px; text-align:right;'>P/O:</td><td>f ±</td></tr>"
            "<tr><td style='padding-right:16px; text-align:right;'>C:</td><td>capture image</td></tr>"
            "</table>"
        )
        help_button.setToolTipDuration(0)  # Show tooltip indefinitely
        
        # Style the tooltip
        help_button.setStyleSheet(help_button.styleSheet() + """
            QToolTip {
                background-color: #3a3a3a;
                border: none;
                border-radius: 4px;
                padding: 4px;
                font-family: 'Consolas';
                font-size: 9pt;
            }
        """)
        
        self.keyboard_controls_toggle = QCheckBox()
        keyboard_controls_layout.addWidget(self.keyboard_controls_toggle, 1, Qt.AlignRight)
        self.keyboard_controls_toggle.setStyleSheet(self.standard_checkbox_style)
        
        # Homing buttons
        self.homing_widget = QWidget()
        machine_controls_layout.addWidget(self.homing_widget)
        homing_layout = QHBoxLayout(self.homing_widget)
        homing_layout.setContentsMargins(10, 5, 10, 5)

        self.homing_label = QLabel("Home axes")
        homing_layout.addWidget(self.homing_label)
        self.homing_label.setStyleSheet(self.standard_label_font)
        self.homing_label.setFont(tab_font)
        homing_layout.addStretch()

        for axis, axis_name in enumerate(["θ", "φ", "h", "all"]):
            button = QPushButton(axis_name)
            button.setStyleSheet(self.standard_button_style)
            button.clicked.connect(lambda checked, a=axis: self.home_axis(a))
            homing_layout.addWidget(button)

        self.camera_connect_widget = QWidget()
        machine_controls_layout.addWidget(self.camera_connect_widget)
        camera_connect_layout = QHBoxLayout(self.camera_connect_widget)
        camera_connect_layout.setContentsMargins(10, 5, 10, 5)

        camera_connect_label = QLabel("Connect to camera")
        camera_connect_layout.addWidget(camera_connect_label)
        camera_connect_label.setStyleSheet(self.standard_label_font)
        
        self.camera_connect_checkbox = QCheckBox()
        camera_connect_layout.addWidget(self.camera_connect_checkbox, 1, Qt.AlignRight)
        self.camera_connect_checkbox.setStyleSheet(self.standard_checkbox_style)
        self.camera_connect_checkbox.clicked.connect(self.toggle_camera_connection)

        # Add capture button
        self.capture_button = QPushButton("CAPTURE")
        self.capture_button.setFixedHeight(70)
        self.capture_button.setStyleSheet(self.standard_button_style_long)
        self.capture_button.clicked.connect(lambda: self.capture_image(format="IIQ"))
        machine_controls_layout.addWidget(self.capture_button)

        machine_controls_layout.addStretch()

#endregion
#region
#region
        ### Populate "Latest Image Captured" tab ###
        last_image_layout = QVBoxLayout(self.last_image)
#endregion
#region
#region

        ### Populate "Capture Sequence" tab ###
        capture_sequence_layout = QVBoxLayout(self.capture_sequence)

        sequence_type_widget = QWidget()
        capture_sequence_layout.addWidget(sequence_type_widget)
        sequence_type_layout = QHBoxLayout(sequence_type_widget)
        sequence_type_layout.setContentsMargins(10, 5, 10, 5)

        sequence_type_label = QLabel("Sequence type")
        sequence_type_layout.addWidget(sequence_type_label)
        sequence_type_label.setStyleSheet(self.standard_label_font)

        sequence_type_dropdown = QComboBox()
        sequence_type_layout.addWidget(sequence_type_dropdown, stretch=1, alignment=Qt.AlignRight)
        sequence_type_dropdown.setMinimumWidth(250)
        sequence_type_dropdown.addItems(["Spin set", "Fibonacci sphere", "Calibration set"])
        sequence_type_dropdown.setStyleSheet("""
            QComboBox {
                background-color: #3a3a3a;
                font-size: 9pt;
            }
            QComboBox:hover {
                background-color: #4a4a4a;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #E0E0E0;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: #3a3a3a;
                selection-background-color: #4a4a4a;
            }
        """)

        self.capture_sequence_stack = QStackedWidget()
        capture_sequence_layout.addWidget(self.capture_sequence_stack)
        self.capture_sequence_stack.currentChanged.connect(self.capture_sequence_stack_switch)
        self.capture_sequence_stack.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        # Connect dropdown to stack after both are created
        sequence_type_dropdown.currentIndexChanged.connect(self.capture_sequence_stack.setCurrentIndex)

        ## Spin set controls ##
        spin_set_widget = QWidget()
        self.capture_sequence_stack.addWidget(spin_set_widget)
        
        spin_set_layout = QVBoxLayout(spin_set_widget)
        spin_set_layout.setContentsMargins(0, 0, 0, 0)
        
        # Checkbox that enables reading from file
        spin_set_file_options = QWidget()
        spin_set_layout.addWidget(spin_set_file_options)
        spin_set_file_options_layout = QHBoxLayout(spin_set_file_options)

        spin_set_file_label = QLabel("Read capture positions from file")
        spin_set_file_label.setStyleSheet(self.standard_label_font)
        spin_set_file_options_checkbox = QCheckBox()
        spin_set_file_options_checkbox.setStyleSheet(self.standard_checkbox_style)
        spin_set_file_options_layout.addWidget(spin_set_file_label)
        spin_set_file_options_layout.addWidget(spin_set_file_options_checkbox, 1, Qt.AlignRight)
        spin_set_file_options_layout.setContentsMargins(10, 5, 10, 5)

        # File selector widget (initially hidden)
        self.spin_set_file_selector = QWidget()
        spin_set_layout.addWidget(self.spin_set_file_selector)
        file_selector_layout = QHBoxLayout(self.spin_set_file_selector)
        file_selector_layout.setContentsMargins(10, 5, 10, 5)

        self.file_path_line_edit = QLineEdit()
        self.file_path_line_edit.setPlaceholderText("Select positions file...")
        self.file_path_line_edit.setReadOnly(True)
        self.file_path_line_edit.setStyleSheet("""
            QLineEdit {
                background-color: #3a3a3a;
                font-size: 9pt;
            }
        """)
        file_selector_layout.addWidget(self.file_path_line_edit)
        
        browse_button = QPushButton("Browse")
        browse_button.setStyleSheet(self.standard_button_style)
        browse_button.clicked.connect(lambda: self.browse_positions_file(self.file_path_line_edit))
        file_selector_layout.addWidget(browse_button)
        
        # Initially hide the file selector
        self.spin_set_file_selector.setVisible(False)
        
        # Connect checkbox to show/hide file selector
        spin_set_file_options_checkbox.toggled.connect(self.use_positions_file_mode)
        
        # Number of rows widget
        spin_set_rows_widget = QWidget()
        spin_set_layout.addWidget(spin_set_rows_widget)
        spin_set_rows_layout = QHBoxLayout(spin_set_rows_widget)
        spin_set_rows_layout.setContentsMargins(10, 5, 10, 5)
        
        rows_label = QLabel("Number of rows")
        rows_label.setStyleSheet(self.standard_label_font)
        spin_set_rows_layout.addWidget(rows_label)
        
        self.rows_line_edit = QLineEdit()
        self.rows_line_edit.setText("4")
        self.rows_line_edit.setStyleSheet("""
            QLineEdit {
                font-size: 9pt;
                background-color: #3a3a3a;
            }
        """)
        spin_set_rows_layout.addStretch()
        spin_set_rows_layout.addWidget(self.rows_line_edit)

        self.rows_value_label = QLabel()
        self.rows_value_label.setStyleSheet(self.standard_label_font)
        self.rows_value_label.setVisible(False)
        spin_set_rows_layout.addWidget(self.rows_value_label)

        # Number of cols widget
        spin_set_cols_widget = QWidget()
        spin_set_layout.addWidget(spin_set_cols_widget)
        spin_set_cols_layout = QHBoxLayout(spin_set_cols_widget)
        spin_set_cols_layout.setContentsMargins(10, 5, 10, 5)

        cols_label = QLabel("Number of cols")
        cols_label.setStyleSheet(self.standard_label_font)
        spin_set_cols_layout.addWidget(cols_label)

        self.cols_line_edit = QLineEdit()
        self.cols_line_edit.setText("16")
        self.cols_line_edit.setStyleSheet("""
            QLineEdit {
                font-size: 9pt;
                background-color: #3a3a3a;
            }
        """)
        spin_set_cols_layout.addStretch()
        spin_set_cols_layout.addWidget(self.cols_line_edit)

        self.cols_value_label = QLabel()
        self.cols_value_label.setStyleSheet(self.standard_label_font)
        self.cols_value_label.setVisible(False)
        spin_set_cols_layout.addWidget(self.cols_value_label)

        # Multiple focuses per position widget
        spin_set_focus_widget = QWidget()
        spin_set_layout.addWidget(spin_set_focus_widget)
        spin_set_focus_layout = QHBoxLayout(spin_set_focus_widget)
        spin_set_focus_layout.setContentsMargins(10, 5, 10, 5)

        focus_label = QLabel("Multiple focuses per position")
        focus_label.setStyleSheet(self.standard_label_font)
        spin_set_focus_layout.addWidget(focus_label)

        self.focus_checkbox = QCheckBox()
        self.focus_checkbox.setStyleSheet(self.standard_checkbox_style)
        spin_set_focus_layout.addWidget(self.focus_checkbox, 1, Qt.AlignRight)

        # Distance between focuses widget
        focus_distance_widget = QWidget()
        spin_set_layout.addWidget(focus_distance_widget)
        focus_distance_layout = QHBoxLayout(focus_distance_widget)
        focus_distance_layout.setContentsMargins(10, 5, 10, 5)

        focus_distance_label = QLabel("Dist. between focuses")
        focus_distance_label.setStyleSheet(self.standard_label_font)
        focus_distance_layout.addWidget(focus_distance_label)

        self.focus_distance_line_edit = QLineEdit()
        self.focus_distance_line_edit.setText("2.0")
        self.focus_distance_line_edit.setStyleSheet("""
            QLineEdit {
                font-size: 9pt;
                background-color: #3a3a3a;
            }
        """)
        focus_distance_layout.addStretch()
        focus_distance_layout.addWidget(self.focus_distance_line_edit)

        focus_distance_units = QLabel("(mm)")
        focus_distance_units.setStyleSheet(self.standard_label_font)
        focus_distance_layout.addWidget(focus_distance_units)

        # Maximum diameter widget
        max_diameter_widget = QWidget()
        spin_set_layout.addWidget(max_diameter_widget)
        max_diameter_layout = QHBoxLayout(max_diameter_widget)
        max_diameter_layout.setContentsMargins(10, 5, 10, 5)

        max_diameter_label = QLabel("Max diameter of subject")
        max_diameter_label.setStyleSheet(self.standard_label_font)
        max_diameter_layout.addWidget(max_diameter_label)

        self.max_diameter_line_edit = QLineEdit()
        self.max_diameter_line_edit.setText("100.0")
        self.max_diameter_line_edit.setStyleSheet("""
            QLineEdit {
                font-size: 9pt;
                background-color: #3a3a3a;
            }
        """)
        max_diameter_layout.addStretch()
        max_diameter_layout.addWidget(self.max_diameter_line_edit)

        max_diameter_units = QLabel("(mm)")
        max_diameter_units.setStyleSheet(self.standard_label_font)
        max_diameter_layout.addWidget(max_diameter_units)

        ## Fibonacci sphere controls ##
        fibonacci_widget = QWidget()
        self.capture_sequence_stack.addWidget(fibonacci_widget)
        self.capture_sequence_stack.adjustSize()

        ## Calibration set controls ##
        calibrate_widget = QWidget()
        self.capture_sequence_stack.addWidget(calibrate_widget)

        # calibrate_layout = QVBoxLayout(calibrate_widget)

        # Button for starting sequence
        calibrate_button_container = QWidget()
        capture_sequence_layout.addWidget(calibrate_button_container)
        calibrate_button_layout = QHBoxLayout(calibrate_button_container)
        calibrate_button_layout.setContentsMargins(0, 0, 0, 0)

        self.calibrate_button = QPushButton("START")
        self.calibrate_button.setFixedHeight(70)
        self.calibrate_button.setStyleSheet(self.standard_button_style_long)
        self.calibrate_button.clicked.connect(self.start_sequence)
        calibrate_button_layout.addWidget(self.calibrate_button)

        # Create cancel button (initially hidden)
        self.calibrate_cancel_button = QPushButton("⨉")
        calibrate_button_layout.addWidget(self.calibrate_cancel_button)
        self.calibrate_cancel_button.setFixedSize(70, 70)
        self.calibrate_cancel_button.setStyleSheet(self.standard_button_style_long)
        self.calibrate_cancel_button.setVisible(False)
        self.calibrate_cancel_button.clicked.connect(self.cancel_sequence)

        capture_sequence_layout.addStretch()

        # On startup, the capture view is displayed first.
        self.run_capture_view()


    def on_tab_changed(self, index):

        # Live View
        if index == 1:
            self.run_live_view()
        elif index == 0:
            self.run_capture_view()

    def run_live_view(self):
        self.camera.SetLiveViewEnable(True)
        thread = QThread()
        worker = LiveViewWorker(self.camera)
        worker.moveToThread(thread)
        thread.started.connect(worker.start)
        worker.live_view_frame_ready.connect(self.live_view.on_frame)
        self.live_view_worker = worker
        self.live_view_thread = thread
        thread.start()


    def run_capture_view(self):

        # Shut down live view processes, in case they are running
        if self.live_view_worker:
            self.live_view_worker.stop()
            self.live_view_thread.quit()
            self.live_view_thread.wait()
            self.live_view_worker = None
            self.live_view_thread = None

        folder = Path(self.capture_directory)
        image_exts = {".iiq"}
        files = [f for f in folder.iterdir() if f.suffix.lower() in image_exts and f.is_file()]
        if files:
            newest = max(files, key=lambda f: f.stat().st_ctime)
            self.display_image(newest)


#endregion

    def output_to_terminal(self, message):
        self.terminal_output.append("> " + message)

    def process_command_input(self):
        """Process user command input"""
        command = self.command_input.text().strip()
        if command is not None:
            self.waiting_for_input = False
            self.last_command = command
            if command != "":
                self.output_to_terminal(command)
            self.command_input.clear()
            self.user_txt_input.emit(command)
    
    def wait_for_user_txt_input(self):
        loop = QEventLoop()
        text_entered = None

        def on_text_entered(text):
            nonlocal text_entered
            text_entered = text
            loop.quit() 

        self.user_txt_input.connect(on_text_entered)
        loop.exec_()
        self.user_txt_input.disconnect(on_text_entered)
        return text_entered
    
    def wait_for_all_motors_stopped(self):
        loop = QEventLoop()

        def on_all_motors_stopped():
            loop.quit()

        self.all_motors_stopped.connect(on_all_motors_stopped)
        loop.exec_()
        self.all_motors_stopped.disconnect(on_all_motors_stopped)

    def disable_manual_controls(self):
        self.geo_grid.setEnabled(False)
        self.keyboard_controls_toggle.setChecked(False)
        self.keyboard_controls_widget.setEnabled(False)
        self.homing_widget.setEnabled(False)
        self.camera_connect_widget.setEnabled(False)
        self.capture_button.setEnabled(False)

    def enable_manual_controls(self):
        self.geo_grid.setEnabled(True)
        self.keyboard_controls_widget.setEnabled(True)
        self.homing_widget.setEnabled(True)
        self.camera_connect_widget.setEnabled(True)
        self.capture_button.setEnabled(True)

    def start_sequence(self):
        self.calibrate_button.setText("IN PROGRESS")
        self.calibrate_button.setStyleSheet(self.standard_button_style_long_in_progress)
        self.calibrate_button.setEnabled(False)
        self.calibrate_cancel_button.setVisible(True)
        self.machine_controls.setEnabled(False)

        match self.capture_sequence_stack.currentIndex():
            case 0:
                self.capture_spin_set()
            case 1:
                self.capture_fibonacci_sequence()
            case 2:
                self.calibration_capture()

    def end_sequence(self):
        self.enable_manual_controls()
        self.calibrate_button.setText("START")
        self.calibrate_button.setStyleSheet(self.standard_button_style_long)
        self.calibrate_cancel_button.setVisible(False)
        self.calibrate_button.setEnabled(True)

    def cancel_sequence(self):
        match self.capture_sequence_stack.currentIndex():
            case 0:
                self.output_to_terminal("Spin set capture cancelled")
            case 1:
                self.output_to_terminal("Fibonacci capture cancelled")
            case 2:
                self.output_to_terminal("Calibration capture cancelled")

        self.user_txt_input.emit("abort")
        self.cancel_sequence_flag = True
        self.stop_all_motors()
        self.end_sequence()

    def update_position_colors(self):
        for axis in range(3):
            le = self.geo[axis]['pos_line_edit']
            if self.motor_data[axis]["position"] is not None:
                # If position does not match, set to unmatched color
                if abs(self.motor_data[axis]["position"] - float(le.text())) > 1e-3:
                    # print("unmatched")
                    le.setStyleSheet(self.pos_line_edit_unmatched_style)
                else:
                    # print("matched")
                    le.setStyleSheet(self.pos_line_edit_matched_style)

    def position_focus_in(self, event, axis, le):
        """Handle when user starts editing a position field"""
        self.actively_editing_position[axis] = True
        print("position in focus")
        # self.update_positions[axis] = False  # Stop automatic updates while editing
        QLineEdit.focusInEvent(le, event)

    def position_focus_out(self, event, axis, le):
        """Handle when user stops editing a position field"""
        self.actively_editing_position[axis] = False
        QLineEdit.focusOutEvent(le, event)
        if axis < 3:
            self.new_position_entered(axis)

    def rate_line_edit_focus_out(self, event, rate_type, axis, line_edit, slider):
        QLineEdit.focusOutEvent(line_edit, event)

        # Clamp line edit value to valid range and update both line edit and slider
        text = line_edit.text()
        value = int(text)
        if value > 100:
            value = 100
        elif value < 1:
            value = 1
        line_edit.setText(str(value))
        slider.setValue(value)

        self.new_rate_entered(axis, rate_type)

    def capture_sequence_stack_switch(self, index):
        for i in range(self.capture_sequence_stack.count()):
            widget = self.capture_sequence_stack.widget(i)
            widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum if i == index else QSizePolicy.Ignored)
        self.capture_sequence_stack.adjustSize()

    def browse_positions_file(self, line_edit):
        """Open file dialog to select position file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Positions File",
            os.path.dirname(os.getcwd()) + "/spin_positions",
            "CSV Files (*.csv)"
        )
        if file_path:
            self.file_path_line_edit.setText(file_path)
            self.parseCSV(file_path)
            print(self.spin_rows, self.spin_cols)

    def use_positions_file_mode(self, checked):
        if checked:
            self.spin_set_file_selector.setVisible(True)
            self.rows_line_edit.setVisible(False)
            self.cols_line_edit.setVisible(False)
            self.rows_value_label.setText("?")
            self.cols_value_label.setText("?")
            self.rows_value_label.setVisible(True)
            self.cols_value_label.setVisible(True)
        else:
            self.spin_set_file_selector.setVisible(False)
            self.file_path_line_edit.setText("")
            self.rows_line_edit.setVisible(True)
            self.cols_line_edit.setVisible(True)
            self.rows_value_label.setVisible(False)
            self.cols_value_label.setVisible(False)

    def parseCSV(self, file_path):
        with open(file_path, 'r') as f:
            reader = csv.reader(f)
            data = list(reader)
            active_section = None
            self.spin_rows = []
            self.spin_cols = []
            for line in data:
                if line:
                    if line[0].startswith("#"):
                        continue
                    elif line[0].startswith("rows"):
                        active_section = "rows"
                        continue
                    elif line[0].startswith("cols"):
                        active_section = "cols"
                        continue
                    if active_section == "rows":
                        try:
                            phi = float(line[0])
                            h = float(line[1])
                        except ValueError:
                            self.output_to_terminal("CSV file is not formatted correctly")
                            return
                        self.spin_rows.append([phi, h])
                    elif active_section == "cols":
                        try:
                            theta = float(line[0])
                        except ValueError:
                            self.output_to_terminal("CSV file is not formatted correctly")
                            return
                        self.spin_cols.append(theta)
        
        self.rows_value_label.setText(str(len(self.spin_rows)))
        if self.spin_cols:
            self.cols_value_label.setText(str(len(self.spin_cols)))
        else:
            self.cols_value_label.setVisible(False)
            self.cols_line_edit.setVisible(True)

    def keyPressEvent(self, event):
        """Handle key press events"""
        if self.keyboard_controls_toggle.isChecked() and not event.isAutoRepeat():
            key = event.key()
            if key in [Qt.Key_A, Qt.Key_D, Qt.Key_W, Qt.Key_S, Qt.Key_E, Qt.Key_Q, Qt.Key_P, Qt.Key_O, Qt.Key_C]:
                self.pressed_keys.add(key)
                self.process_key(key)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """Handle key release events"""
        if  not event.isAutoRepeat():
            key = event.key()
            if key in self.pressed_keys:
                self.pressed_keys.discard(key)
                if key in [Qt.Key_A, Qt.Key_D]:
                    self.stop_motor(0)
                elif key in [Qt.Key_W, Qt.Key_S]:
                    self.stop_motor(1)
                elif key in [Qt.Key_E, Qt.Key_Q]:
                    self.stop_motor(2)
            super().keyReleaseEvent(event)

    def process_keyboard_commands(self):
        """Process held down keys periodically"""
        if self.keyboard_controls_toggle.isChecked():
            for key in self.pressed_keys:
                if key != Qt.Key_C:  # Don't repeat camera capture
                    self.process_key(key)

    def process_key(self, key):
        """Process individual key commands"""
        if key == Qt.Key_A:
            self.increment_position(0, 1)  # θ + 10 degrees
        elif key == Qt.Key_D:
            self.increment_position(0, -1)  # θ - 10 degrees
        elif key == Qt.Key_W:
            self.increment_position(1, 1)  # φ + 10 degrees
        elif key == Qt.Key_S:
            self.increment_position(1, -1)  # φ - 10 degrees
        elif key == Qt.Key_E:
            self.increment_position(2, 1)  # h + 10 mm
        elif key == Qt.Key_Q:
            self.increment_position(2, -1)  # h - 10 mm
        elif key == Qt.Key_P:
            self.increment_position(3, 1)  # f + 10 mm
        elif key == Qt.Key_O:
            self.increment_position(3, -1)  # f - 10 mm
        # elif key == Qt.Key_C:
    #         self.capture_image()

    ### CAMERA RELATED FUNCTIONS ###

    def initialize_camera(self):
        try:
            self.camera = Camera.OpenUsbCamera()
            self.output_to_terminal("Camera connected") #TODO add camera details
            self.camera_connect_checkbox.setChecked(True)
            self.camera.EnableImageReceiving(True)
            self.camera.SetHostStorageCapacity(1000000) # value in MB
        except Exception as e:
            self.output_to_terminal(f"Unable to connect to camera [{str(e)}]")
            self.camera = None
            self.camera_connect_checkbox.setChecked(False)

    def toggle_camera_connection(self, state):
        if state:
            self.initialize_camera()
        else:
            if self.camera is not None:
                self.camera.Dispose()
                self.camera = None
                self.output_to_terminal("Camera disconnected")
            else:
                print("There was no camera to disconnect")

    ### MACHINE RELATED FUNCTIONS ###

    def home_axis(self, axis):
        if axis < 3:
            self.send_command(f'H{axis}')
        elif axis == 3:
            for a in range(3):
                self.send_command(f'H{a}')
    
    def new_position_entered(self, axis):
        line_edit = self.geo[axis]['pos_line_edit']
        value = line_edit.text()
        # line_edit.clearFocus()
        self.move_to_position(axis, float(value))

    def new_rate_entered(self, type, axis):
        percent = int(self.geo[axis][type + '_line_edit'].text())
        self.set_rate(axis, percent, type)
        # TODO now read rate back from controller and update UI

    def increment_position(self, axis, direction):
        line_edit = self.geo[axis]['pos_line_edit']
        current_position = self.motor_data[axis]['position']
        multiplier = 10000
        match axis:
            case 0:  # theta
                step = 2
            case 1:  # phi
                step = 2
            case 2:  # h
                step = 4
            case 3:  # f
                step = 2.0 
        line_edit.setText(f"{current_position + direction * step:.4f}")
        self.move_to_position(axis, current_position + direction * step * multiplier)

    def setup_serial_polling(self):
        """Setup timer to poll microcontroller for serial output"""
        self.serial_timer = QTimer()
        self.serial_timer.timeout.connect(self.poll_serial)
        self.serial_timer.start(100)  # Poll every 100ms, must be greater than microcontroller estop delay (50ms)

    def initialize_hardware(self):
        # Connect to microcontroller
        try:
            self.serial = serial.Serial('COM3', 115200, dsrdtr=True)
            self.serial.write('\r\n\r\n'.encode())
            self.serial.flushInput()
            self.microcontroller_connected = True
            self.output_to_terminal("Microcontroller connected")
        except Exception as e:
            self.output_to_terminal(f"Unable to connect to microcontroller: {str(e)}")
        if self.microcontroller_connected:
            self.poll_serial()
            self.request_rates()

        # Connect to camera
        self.initialize_camera()

    def poll_serial(self):
        if self.microcontroller_connected:
            estop_signal_detected = False
            while self.serial.in_waiting:
                line_full = self.serial.readline().decode().strip()
                line = line_full.split()
                if line:
                    if line[0] == "P":
                        # print(line)
                        # print(self.motor_data)
                        for axis in range(3):
                            is_running = int(line[axis * 2 + 1])
                            pos_in_steps = int(line[axis * 2 + 2])
                            position = self.steps_to_position(axis, pos_in_steps)

                            # if is_running's state changed to false, update position display
                            if self.motor_data[axis]["is_running"] is not None and self.motor_data[axis]["is_running"] != is_running and not is_running:
                                self.update_positions[axis] = True

                                # check is we need to emit all_motors_stopped
                                other_axes = [i for i in range(3) if i != axis]
                                if all(not self.motor_data[i]["is_running"] for i in other_axes):
                                    self.all_motors_stopped.emit()

                            self.motor_data[axis]["is_running"] = is_running
                            self.motor_data[axis]["position"] = position
                            if self.update_positions[axis]:
                                self.geo[axis]['pos_line_edit'].setText(f"{position:.4f}")
                                self.update_positions[axis] = False
                    elif line[0] == "R":
                        for axis in range(3):
                            speed = float(line[axis * 2 + 1])
                            accel = float(line[axis * 2 + 2])
                            speed_percent = self.rate_to_percentage(speed)
                            self.motor_data[axis]["speed"] = speed_percent
                            self.geo[axis]['speed_slider'].setValue(speed_percent)
                            accel_percent = self.rate_to_percentage(accel)
                            self.motor_data[axis]["accel"] = accel_percent
                            self.geo[axis]['accel_slider'].setValue(accel_percent)
                    elif line[0] == "N":
                        self.needs_homing_flag = True
                        self.output_to_terminal("All axes must be homed before continuing operation")
                        for axis in range(3):
                            self.update_positions[axis] = True
                    elif line[0] == "H":
                        axis = int(line[1])
                        self.homing[axis] = False
                    elif line[0] == "E":
                        estop_signal_detected = True
                    # elif line[0] == "A":
                    #     self.alarm_flag = True
                    # elif line[0] == "W":
                    #     self.wrong_direction_flag = True
                    else:
                        print("Received invalid serial code from microcontroller: " + line_full)
                
            self.send_command('P')

            if estop_signal_detected and not self.estop_pressed:
                self.estop_pressed = True
                self.output_to_terminal("Emergency stop button has been pressed. Please release the button to re-enable the machine.")
                self.machine_controls.setEnabled(False)
            elif not estop_signal_detected and self.estop_pressed:
                self.estop_pressed = False
                self.output_to_terminal("Emergency stop button has been released")
                self.machine_controls.setEnabled(True)

            if not any(self.actively_editing_position):
                self.update_position_colors()
    
    def request_rates(self):
        self.send_command('R')

    def send_command(self, command):
        if self.microcontroller_connected:
            l = command.strip() # Strip all EOL characters for consistency
            command_nl = l + '\n'
            self.serial.write(command_nl.encode())
            if not l.endswith('P'):
                print("Sent command to microcontroller: " + command_nl.strip())

    def steps_to_position(self, axis, steps):
        return float(steps)
    
    def position_to_steps(self, axis, position):
        return int(position)
    
    def rate_to_percentage(self, rate):
        return int(100 * rate / 4000.0)
    
    def percentage_to_rate(self, percentage):
        return int((percentage / 100.0) * 4000.0)

    def move_to_position(self, axis, position):
        steps = self.position_to_steps(axis, position)
        sign = '-' if steps < 0.0 else '+'
        self.send_command("M" + str(axis) + sign + str(abs(steps)))

    def set_rate(self, axis, percent, type):
        rate = self.percentage_to_rate(percent)
        if type == "speed":
            self.send_command("S" + str(axis) + "+" + str(rate))
            # TODO now read speed back from controller and update UI
        elif type == "accel":
            self.send_command("A" + str(axis) + "+" + str(rate))
            # TODO now read speed back from controller and update UI
        
    def stop_all_motors(self):
        for i in range(3):
            self.stop_motor(i)

    def stop_motor(self, axis):
        self.send_command("E" + str(axis))

    ### CAPTURE SEQUENCE RELATED FUNCTIONS ###
    def move_capture_wait(self, theta, phi, h):
        self.move_to_position(0, theta)
        self.move_to_position(1, phi)
        self.move_to_position(2, h)
        self.wait_for_all_motors_stopped()
        self.capture_image()

    def capture_spin_set(self):
        self.output_to_terminal("Starting spin set capture sequence...")
        if self.rows_value_label.isVisible():
            row_values = self.spin_rows
        else:
            num_rows = int(self.rows_line_edit.text())
            phi_values = np.linspace(0, 90, num=num_rows, endpoint=False).tolist()
            h = float(self.geo_grid[2]['pos_line_edit'].text())
            row_values = [[phi, h] for phi in phi_values]
        if self.cols_value_label.isVisible():
            col_values = self.spin_cols
        else:
            num_cols = int(self.cols_line_edit.text())
            col_values = np.linspace(0, 360, num=num_cols, endpoint=False).tolist()
        
        for r in row_values:
            for c in col_values:
                if self.cancel_sequence_flag:
                    self.cancel_sequence_flag = False
                    self.end_sequence()
                    return
                self.move_capture_wait(c, r[0], r[1])

        self.output_to_terminal("Spin set capture sequence complete")
        self.end_sequence()

    def capture_fibonacci_sequence(self):
        self.output_to_terminal("Starting Fibonacci capture sequence...")
        # TODO: Implement Fibonacci capture logic
        self.output_to_terminal("Fibonacci capture sequence complete")
        self.end_sequence()

    def calibration_capture(self):
        self.output_to_terminal("Starting calibration set capture sequence...")
        # TODO add positioning code back in once we have positions
        # self.output_to_terminal("Moving to calibration position...")
        # self.move_to_position(0, 0.0)  # Reset θ
        # self.move_to_position(1, 90.0)  # Reset φ

        self.output_to_terminal("Place checkerboard target flat on the stage. Use the live " \
        "view to position it near the middle of the right edge of the camera's field of view. " \
        "The entire target should be in frame. Press ENTER to continue.")

        output = self.wait_for_user_txt_input()  # Wait for user to press ENTER
        if output == "abort":
            return
        self.output_to_terminal("Starting calibration capture sequence...")

        # TODO move back to top position
        # TODO capture image
        self.output_to_terminal("Calibration capture sequence complete")
        self.end_sequence()

    def capture_image(self, raw=True, format="IIQ"):
        if self.camera is not None:
            try:
                self.camera.TriggerCapture()
                frame = self.camera.WaitForImage()
                filename = time.strftime("%Y%m%d_%H%M%S")
                path = self.capture_directory + "\\" + filename + ".iiq"
                data = bytes(frame.Data.ToArray())
                with open(path, "wb") as f:
                    f.write(data)
                self.display_image(path)
                self.output_to_terminal(f"Image captured: {path}")
            except Exception as e:
                self.output_to_terminal(f"Failed to capture image: {str(e)}")
        else:
            self.output_to_terminal("No camera connected")


    def display_image(self, path):
        with Image.open(path) as img:
            width, height = img.size
            data = img.tobytes()
            image = QImage(bytes(data), width, height, QImage.Format_RGB888)
            pxmap = QPixmap.fromImage(image)
            self.last_image.setPixmap(pxmap)
        
        
        """
        else:
            raw_image = RwImage(iiq_file.Data.Pointer, iiq_file.Data.Length)
            convert_config = ConvertConfig()
            convert_config.SetOutputWidth(14204)
            bitmap = convert_config.ApplyTo(raw_image)
            if format == "TIFF":
                tiff_config = TiffConfig()
                tiff_config.tileSize = TiffTileSize.tileSize512
                path += ".tif"
                raw_image.WriteAsTiff(path, bitmap, tiff_config)
            elif format == "JPEG":
                jpeg_config = JpegConfig()
                jpeg_config.Quality = 90
                path += ".jpg"
                raw_image.WriteAsJpeg(path, bitmap, jpeg_config)
        """

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QWidget { 
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', sans-serif; 
            color: #E0E0E0;
            font-size: 9pt;
            border: none;
        }
        
        /* Base styles */
        QLineEdit {
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 12pt;
        }
        
        QPushButton {
            background-color: #3a3a3a;
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 9pt;
        }
        QPushButton:hover {
            background-color: #4a4a4a;
        }
        QPushButton:pressed {
            background-color: #2a2a2a;
        }
        
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            background-color: #3a3a3a;
            border-radius: 6px;
        }
        QCheckBox::indicator:checked {
            background-color: #5ccd80;
        }
        QCheckBox::indicator:checked:hover {
            background-color: #6cdd90;
        }
        QCheckBox::indicator:hover {
            background-color: #4a4a4a;
        }
        
        QTabWidget::pane { 
            background-color: #252525;
            border-radius: 6px;
        }
        QTabBar::tab {
            background: #1a1a1a;
            padding: 8px 12px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            font-size: 9pt;
        }
        
        QComboBox {
            border-radius: 6px;
            padding: 4px 8px;
        }
        QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        QComboBox::down-arrow {
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid #E0E0E0;
            margin-right: 5px;
        }
        QComboBox QAbstractItemView {
            background-color: #3a3a3a;
            selection-background-color: #4a4a4a;
        }
        
        QSlider::groove:horizontal {
            border-radius: 3px;
        }
        QSlider::handle:horizontal {
            border-radius: 6px;
        }
        
        QToolTip {
            background-color: #3a3a3a;
            border-radius: 6px;
            padding: 4px;
            font-family: 'Consolas';
            font-size: 9pt;
        }
        
        QTextEdit { 
            border-radius: 6px;
        }
    """)
    window = ControlUI()
    window.show()
    app.exec()

    # if camera is not None:
    # camera.Close()
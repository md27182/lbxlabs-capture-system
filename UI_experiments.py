# file: camera_control_ui.py

import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QComboBox,
    QVBoxLayout, QHBoxLayout, QGroupBox, QTextEdit, QPushButton, QCheckBox, QDialog,
    QSizePolicy, QTabWidget  # Add QTabWidget
)
from PyQt5.QtGui import QPixmap, QPalette, QColor, QIcon, QCursor
from PyQt5.QtCore import Qt, QTimer, QPoint


class CameraControlUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("lbxcontrol")
        self.setGeometry(100, 100, 1000, 600)
        self.set_dark_theme()
        self.init_ui()
        self.theta, self.phi, self.h, self.focus = 0, 0, 0, 0
        self.setFocusPolicy(Qt.StrongFocus)  # Ensure widget can accept focus
        self.setFocus()  # Explicitly set focus to this widget
        self.jog_enabled = True  # Track jog state
        self.tooltip_label = None  # For custom tooltip

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

    def init_ui(self):
        self.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #E0E0E0;
                padding: 4px;
            }
            QWidget {
                background-color: #1e1e1e;
                border: none;
            }
            QLabel#TitleLabel {
                font-size: 18px;
                font-weight: bold;
                color: #FFFFFF;
            }
            QGroupBox {
                border: 1px solid #444;
                border-radius: 6px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: #CCCCCC;
            }
        """)

        # Initialize all widgets first
        self.pos_label = QLabel("Current Geometry: \nθ=0 \nφ=0 \nh=0 \nFocus=0")
        self.image_label = QLabel("Live View / Captured Image")
        self.sequence_dropdown = QComboBox()
        self.sequence_dropdown.addItems(["Capture Sequence", "Calibration Sequence"])

        # Configure widgets
        self.pos_label.setObjectName("TitleLabel")
        self.pos_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.image_label.setFixedSize(640, 480)
        self.image_label.setStyleSheet("border: 2px solid #444; background-color: #2b2b2b;")
        self.image_label.setAlignment(Qt.AlignCenter)

        # Keyboard control switch + info icon
        keyboard_control_layout = QHBoxLayout()
        keyboard_control_label = QLabel("Enable keyboard controls:")
        keyboard_control_label.setStyleSheet("color: #AAAAAA; font-size: 14px;")

        info_btn = QPushButton("?")
        info_btn.setFixedSize(24, 24)
        info_btn.setStyleSheet("""
            QPushButton {
                background: #222;
                color: #00FF99;
                border: none;
                font-size: 16px;
                border-radius: 12px;
            }
        """)
        info_btn.installEventFilter(self)
        self.info_btn = info_btn  # Save reference for eventFilter

        self.jog_switch = QCheckBox()
        self.jog_switch.setChecked(False)  # Start in the off state
        self.jog_enabled = False           # Sync jog_enabled with switch
        self.jog_switch.setStyleSheet("""
            QCheckBox::indicator {
                width: 32px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border-radius: 9px;
                background: #444;
                border: 1px solid #888;
            }
            QCheckBox::indicator:checked {
                border-radius: 9px;
                background: #00FF99;
                border: 1px solid #00FF99;
            }
        """)
        self.jog_switch.stateChanged.connect(self.toggle_jog)
        keyboard_control_layout.addWidget(keyboard_control_label)
        keyboard_control_layout.addWidget(info_btn)
        keyboard_control_layout.addWidget(self.jog_switch)
        keyboard_control_layout.addStretch()

        # Machine Status section (left side)
        left_tabs = QTabWidget()
        left_tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #444; }
            QTabBar::tab {
                background: #222;
                color: #E0E0E0;
                padding: 8px;
                border: 1px solid #444;
            }
            QTabBar::tab:selected {
                background: #333;
                border-bottom: none;
            }
        """)

        # Just the Status tab
        status_widget = QWidget()
        status_layout = QVBoxLayout()
        status_layout.setAlignment(Qt.AlignTop)
        status_layout.addWidget(self.pos_label)
        status_layout.addLayout(keyboard_control_layout)
        status_layout.addStretch()  # Fill vertical space
        status_widget.setLayout(status_layout)
        left_tabs.addTab(status_widget, "Machine Status")

        left_layout = QVBoxLayout()
        left_layout.addWidget(left_tabs)

        # Camera section (center) - Live View only
        center_tabs = QTabWidget()
        center_tabs.setStyleSheet(left_tabs.styleSheet())

        live_view_widget = QWidget()
        image_layout = QVBoxLayout()
        image_layout.addWidget(self.image_label)
        image_layout.addStretch()  # Fill vertical space
        live_view_widget.setLayout(image_layout)
        center_tabs.addTab(live_view_widget, "Live View")

        center_layout = QVBoxLayout()
        center_layout.addWidget(center_tabs)

        # Settings tabs (right side)
        right_tabs = QTabWidget()
        right_tabs.setStyleSheet(left_tabs.styleSheet())

        # Machine Settings tab
        settings_widget = QWidget()
        machine_settings_layout = QVBoxLayout()
        machine_settings_layout.setAlignment(Qt.AlignTop)
        machine_settings_layout.addStretch()  # Fill vertical space
        settings_widget.setLayout(machine_settings_layout)
        right_tabs.addTab(settings_widget, "Machine Settings")

        # Camera Settings tab
        camera_settings_widget = QWidget()
        camera_settings_layout = QVBoxLayout()
        camera_settings_layout.setAlignment(Qt.AlignTop)
        camera_settings_layout.addStretch()  # Fill vertical space
        camera_settings_widget.setLayout(camera_settings_layout)
        right_tabs.addTab(camera_settings_widget, "Camera Settings")

        # Execute Sequence tab
        sequence_widget = QWidget()
        sequence_layout = QVBoxLayout()
        sequence_layout.setAlignment(Qt.AlignTop)
        sequence_layout.addWidget(self.sequence_dropdown)
        sequence_layout.addStretch()  # Fill vertical space
        sequence_widget.setLayout(sequence_layout)
        right_tabs.addTab(sequence_widget, "Execute Sequence")

        right_layout = QVBoxLayout()
        right_layout.addWidget(right_tabs)

        # Set size policies for proper expansion
        left_tabs.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        center_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_tabs.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        horizontal_layout = QHBoxLayout()
        horizontal_layout.setSpacing(20)
        horizontal_layout.setContentsMargins(20, 20, 20, 20)
        horizontal_layout.addLayout(left_layout, 0)    # No horizontal stretch
        horizontal_layout.addLayout(center_layout, 1)  # Horizontal stretch
        horizontal_layout.addLayout(right_layout, 0)   # No horizontal stretch

        # Container widget for main UI
        main_ui_widget = QWidget()
        main_ui_widget.setLayout(horizontal_layout)

        # Terminal-like window
        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setFixedHeight(120)  # Approximately 6 lines
        self.terminal_output.setStyleSheet("""
            background-color: #181818; 
            color: #FFFFFF; 
            font-family: 'Consolas'; 
            font-size: 14px; 
            border: 2px solid #444; 
            border-radius: 6px;
        """)

        terminal_layout = QVBoxLayout()
        terminal_layout.setSpacing(2)
        terminal_layout.setContentsMargins(20, 0, 20, 20)  # Match horizontal_layout margins
        terminal_layout.addWidget(self.terminal_output)

        # Container widget for terminal
        terminal_widget = QWidget()
        terminal_widget.setLayout(terminal_layout)

        # Main vertical layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(main_ui_widget)
        main_layout.addWidget(terminal_widget)
        self.setLayout(main_layout)

    def toggle_jog(self):
        self.jog_enabled = self.jog_switch.isChecked()

    def keyPressEvent(self, event):
        if not self.jog_enabled:
            return
        key = event.key()
        moved = False
        if key == Qt.Key_A:
            self.theta -= 1
            moved = True
        elif key == Qt.Key_D:
            self.theta += 1
            moved = True
        elif key == Qt.Key_W:
            self.phi += 1
            moved = True
        elif key == Qt.Key_S:
            self.phi -= 1
            moved = True
        elif key == Qt.Key_Q:
            self.h += 1
            moved = True
        elif key == Qt.Key_E:
            self.h -= 1
            moved = True
        elif key == Qt.Key_C:
            self.capture_image()

        if moved:
            self.update_position_display()

    def update_position_display(self):
        self.pos_label.setText(
            f"Current Geometry: \nθ={self.theta} \nφ={self.phi} \nh={self.h} \nFocus={self.focus}"
        )

    def capture_image(self):
        pass

    def show_custom_tooltip(self, widget):
        tooltip_text = (
            "Keyboard Controls:<br>"
            "<table style='border-collapse:collapse;'>"
            "<tr><td style='padding-right:16px; text-align:right;'>A:</td><td>θ + 10 degrees</td></tr>"
            "<tr><td style='padding-right:16px; text-align:right;'>D:</td><td>θ - 10 degrees</td></tr>"
            "<tr><td colspan='2'>&nbsp;</td></tr>"
            "<tr><td style='padding-right:16px; text-align:right;'>W:</td><td>φ + 10 degrees</td></tr>"
            "<tr><td style='padding-right:16px; text-align:right;'>S:</td><td>φ - 10 degrees</td></tr>"
            "<tr><td colspan='2'>&nbsp;</td></tr>"
            "<tr><td style='padding-right:16px; text-align:right;'>E:</td><td>h + 10 mm</td></tr>"
            "<tr><td style='padding-right:16px; text-align:right;'>Q:</td><td>h - 10 mm</td></tr>"
            "<tr><td colspan='2'>&nbsp;</td></tr>"
            "<tr><td style='padding-right:16px; text-align:right;'>P:</td><td>focus + 10 mm</td></tr>"
            "<tr><td style='padding-right:16px; text-align:right;'>O:</td><td>focus - 10 mm</td></tr>"
            "<tr><td colspan='2'>&nbsp;</td></tr>"
            "<tr><td style='padding-right:16px; text-align:right;'>C:</td><td>capture image</td></tr>"
            "</table>"
        )
        if hasattr(self, "tooltip_dialog") and self.tooltip_dialog is not None:
            self.tooltip_dialog.close()
            self.tooltip_dialog = None

        self.tooltip_dialog = QDialog(self, Qt.FramelessWindowHint | Qt.Popup)
        self.tooltip_dialog.setAttribute(Qt.WA_TranslucentBackground)
        layout = QVBoxLayout(self.tooltip_dialog)
        label = QLabel(tooltip_text)
        label.setStyleSheet("""
            background-color: #222;
            color: #E0E0E0;
            border: 1px solid #444;
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 14px;
        """)
        label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        label.setTextFormat(Qt.RichText)
        layout.addWidget(label)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tooltip_dialog.setLayout(layout)
        btn_pos = widget.mapToGlobal(widget.rect().bottomLeft())
        self.tooltip_dialog.move(btn_pos.x(), btn_pos.y() + 8)
        self.tooltip_dialog.adjustSize()
        self.tooltip_dialog.show()

    def eventFilter(self, obj, event):
        if obj is getattr(self, "info_btn", None):
            if event.type() == event.Enter:
                self.show_custom_tooltip(obj)
            elif event.type() == event.Leave:
                if hasattr(self, "tooltip_dialog") and self.tooltip_dialog is not None:
                    self.tooltip_dialog.close()
                    self.tooltip_dialog = None
        # Remove code that handles tooltip_dialog leave events
        return super().eventFilter(obj, event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CameraControlUI()
    window.show()
    sys.exit(app.exec())


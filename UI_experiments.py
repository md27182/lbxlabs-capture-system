# file: camera_control_ui.py

import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QComboBox,
    QVBoxLayout, QHBoxLayout, QGroupBox, QFrame
)
from PyQt5.QtGui import QPixmap, QPalette, QColor
from PyQt5.QtCore import Qt


class CameraControlUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3-Axis Camera Controller")
        self.setGeometry(100, 100, 1000, 600)
        self.set_dark_theme()
        self.init_ui()
        self.theta, self.phi, self.h, self.focus = 0, 0, 0, 0

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
            QLabel#JogInfo {
                font-size: 13px;
                color: #AAAAAA;
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

        self.pos_label = QLabel("Position: \nθ=0 \nφ=0 \nh=0 \nFocus=0")
        self.pos_label.setObjectName("TitleLabel")
        self.pos_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.jog_info = QLabel("Jog using keys: A/D (θ), W/S (φ), Q/E (h)\nAdjust focus: +/-\nCapture image: C")
        self.jog_info.setObjectName("JogInfo")
        self.jog_info.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        status_layout = QVBoxLayout()
        status_layout.addWidget(self.pos_label)
        status_layout.addWidget(self.jog_info)

        status_box = QGroupBox("Machine Status")
        status_box.setLayout(status_layout)

        settings_machine = QGroupBox("Machine Settings")
        settings_machine.setLayout(QVBoxLayout())

        left_layout = QVBoxLayout()
        left_layout.addWidget(status_box)
        left_layout.addWidget(settings_machine)

        self.image_label = QLabel("Live View / Captured Image")
        self.image_label.setFixedSize(640, 480)
        self.image_label.setStyleSheet("border: 2px solid #444; background-color: #2b2b2b;")
        self.image_label.setAlignment(Qt.AlignCenter)

        image_layout = QVBoxLayout()
        image_layout.addWidget(self.image_label)

        image_box = QGroupBox("Live View")
        image_box.setLayout(image_layout)

        settings_camera = QGroupBox("Camera Settings")
        settings_camera.setLayout(QVBoxLayout())

        center_layout = QVBoxLayout()
        center_layout.addWidget(image_box)
        center_layout.addWidget(settings_camera)

        self.sequence_dropdown = QComboBox()
        self.sequence_dropdown.addItems(["Capture Sequence", "Calibration Sequence"])
        sequence_layout = QVBoxLayout()
        sequence_layout.addWidget(self.sequence_dropdown)

        dropdown_box = QGroupBox("Execute Sequence")
        dropdown_box.setLayout(sequence_layout)

        right_layout = QVBoxLayout()
        right_layout.addWidget(dropdown_box)
        right_layout.addStretch()

        horizontal_layout = QHBoxLayout()
        horizontal_layout.setSpacing(20)
        horizontal_layout.setContentsMargins(20, 20, 20, 20)
        horizontal_layout.addLayout(left_layout)
        horizontal_layout.addLayout(center_layout)
        horizontal_layout.addLayout(right_layout)

        self.setLayout(horizontal_layout)

    def keyPressEvent(self, event):
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
        self.pos_label.setText(f"Status: θ={self.theta} φ={self.phi} h={self.h} Focus={self.focus}")

    def capture_image(self):
        pixmap = QPixmap(640, 480)
        pixmap.fill(QColor(60, 60, 60))
        self.image_label.setPixmap(pixmap)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CameraControlUI()
    window.show()
    sys.exit(app.exec())

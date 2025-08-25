# file: camera_control_ui.py

import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QComboBox,
    QVBoxLayout, QHBoxLayout, QGroupBox, QTextEdit, QPushButton, QCheckBox, QDialog,
    QSizePolicy, QTabWidget  # Add QTabWidget
)
from PyQt5.QtGui import QPixmap, QPalette, QColor, QIcon, QCursor, QImage
from PyQt5.QtCore import Qt, QTimer, QPoint, QCoreApplication

# Add reference to the C# SDK DLL
import clr
clr.AddReference(r"CameraSdkCs")
clr.AddReference(r"ImageSdkCs")
from P1.CameraSdk import Camera
from P1.ImageSdk import *
import System
import time

class CameraControlUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("lbxcontrol")
        self.setGeometry(100, 100, 1000, 600)
        self.init_ui()
        self.initialize_camera()

    def init_ui(self):
        main_widget = QLabel("LIVE VIEW WILL APPEAR HERE")
        main_layout = QVBoxLayout(self)
        main_button = QPushButton("DO SOMETHING")
        main_button.clicked.connect(self.button_clicked_function)
        main_layout.addWidget(main_widget)
        main_layout.addWidget(main_button)
        self.main_widget = main_widget

    def button_clicked_function(self):
        self.camera.SetLiveViewEnable(True)
        while True:
            frame = self.camera.WaitForLiveView(1000)
            data = frame.Data.ToArray()
            image = QImage(bytes(data), frame.Width, frame.Height, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(image)
            self.main_widget.setPixmap(pixmap)
            QCoreApplication.processEvents()
            

    def initialize_camera(self):
        self.camera = Camera.OpenUsbCamera()
        self.camera.SetHostStorageCapacity(1000000) # value in MB


    def capture_image(self, raw=True, format="IIQ"):
        if self.camera is not None:
            try:
                self.camera.TriggerCapture()
                iiq_file = self.camera.WaitForImage()

                if not filename:
                    filename = time.strftime("%Y%m%d_%H%M%S")
                path = self.capture_directory + "/" + filename

                if format == "IIQ":
                    path += ".IIQ"
                    img = Image.frombytes('RGB', iiq_file.Data.Length, iiq_file.Data.ToArray())
                    qtimg = ImageQt(img)
                    pxmap = QPixmap.fromImage(qtimg)
                    self.last_image.setPixmap(pxmap)
                    #System.IO.File.WriteAllBytes(path, iiq_file.Data.ToArray())
                else:
                    raw_image = RawImage(iiq_file.Data.Pointer, iiq_file.Data.Length)
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

                self.output_to_terminal(f"Image captured: {path}")
            except Exception as e:
                self.output_to_terminal(f"Failed to capture image: {str(e)}")
        else:
            self.output_to_terminal("No camera connected")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CameraControlUI()
    window.show()
    sys.exit(app.exec())


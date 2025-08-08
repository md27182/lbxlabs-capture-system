import serial
import time
import sys
import os
import glob
import keyboard
import clr

# Add reference to the C# SDK DLL
clr.AddReference(r"CameraSdkCs")
clr.AddReference(r"ImageSdkCs")
from P1.CameraSdk import Camera
from P1.ImageSdk import *
import System

class Microcontroller:
    def __init__(self, serial):
        self.serial = serial
        self.serial.write('\r\n\r\n'.encode())
        time.sleep(2)
        self.serial.flushInput()

    def __del__(self):
        self.serial.close()

    def sendCommand(self, command):
        l = command.strip() # Strip all EOL characters for consistency
        command_nl = l + '\n'
        self.serial.write(command_nl.encode())

def jogMode(controller, camera):
    print('''
        Use the a, s, d, q, w, and e keys to position the system. 
        * stage clockwise/counterclockwise = a/d
        * carriage up/down = w/s
        * camera nod forward/backward = e/q
        Press escape to exit this mode.
        ''')
    
    STAGE_JOG_DISTANCE = 100
    TRACK_JOG_DISTANCE = 1000
    NOD_JOG_DISTANCE = 100

    while True:
        if keyboard.is_pressed('a'):
            controller.sendCommand('J0+' + str(STAGE_JOG_DISTANCE))
        if keyboard.is_pressed('d'):
            controller.sendCommand('J0-' + str(STAGE_JOG_DISTANCE))
        if keyboard.is_pressed('w'):
            controller.sendCommand('J1+' + str(TRACK_JOG_DISTANCE))
        if keyboard.is_pressed('s'):
            controller.sendCommand('J1-' + str(TRACK_JOG_DISTANCE))
        if keyboard.is_pressed('e'):
            controller.sendCommand('J2+' + str(NOD_JOG_DISTANCE))
        if keyboard.is_pressed('q'):
            controller.sendCommand('J2-' + str(NOD_JOG_DISTANCE))
        if keyboard.is_pressed('c'):
            if camera is not None:
                camera.TriggerCapture()
                image_file = camera.WaitForImage()
                System.IO.File.WriteAllBytes("test_raw.iiq", image_file.Data.ToArray())

                raw_image = RawImage(image_file.Data.Pointer, image_file.Data.Length)

                metadata = MetaDataBase(raw_image)
                success = metadata.CreateXmpNamespace("calibration", "http://www.lbxlabs.com/calibration/");
                if(success):
                    success = metadata.CreateMetaObject("xmp:calibration:extrinsics").SetString("Values of the cameras extrinsic matrix")

                # decodeConfig = DecodeConfig.Defaults();
                # decodedImage = decodeConfig.ApplyTo(raw_image);
                # System.IO.File.WriteAllBytes("bitmapBayer.bin", decodedImage.Data);

                convertConfig = ConvertConfig()
                convertConfig.SetOutputWidth(14204)
                tiffConfig = TiffConfig()
                tiffConfig.tileSize = TiffTileSize.tileSize512
                bitmap = convertConfig.ApplyTo(raw_image)
                raw_image.WriteAsTiff("test_tiff.tiff", bitmap, metadata, tiffConfig)


            # System.IO.File.WriteAllBytes("bitmapRGB.bin", bitmap.Data);
        if keyboard.is_pressed('escape'):
            break

    time.sleep(0.2)

def main():
    controller = Microcontroller(serial.Serial('COM3', 115200))
    camera_connected = False

    try:
        camera = Camera.OpenUsbCamera()
    except:
        print("No camera connected")
        camera = None
    if camera is not None:
        camera.EnableImageReceiving(True)
        camera.SetHostStorageCapacity(1000000) # value in MB

    # for property_id in list(camera.GetAllPropertyIds()):
    #     print(camera.GetPropertySpec(property_id))
    # P1.ImageSDK.Initalize()

    while True:
        val = input('> ')
        if val == 'exit':
            break
        valarr = val.split()
        if valarr:
            if valarr[0] == 'j':
                jogMode(controller, camera)
    
    # if camera is not None:
    # camera.Close()

if __name__ == '__main__':
    sys.exit(main())
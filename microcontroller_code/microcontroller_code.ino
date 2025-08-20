/*

Stage motor = motor that controls the stage
Track motor = motor that moves the carriage up and down
Nod motor = motor that nods the camera up and down

The PC sends serial commands to this program which then parses them and executes them.
Serial command format: [command type][axis][sign indicator][value]
  command type = 'M' (move to position), 'J' (jog by amount), 'S' (set speed), 'A' (set acceleration), 'H' (home axis), 'F' (force)
  axis = '0' (stage), '1' (track), '2' (nod)
  sign indicator = '+' or '-'
  value = integer with up to MAX_DIGITS digits; for home axis commands the options are +1 or -1 depending on which switch you want to use

The controller also sends codes back to the PC to communicate the status of the machine.
There are 4 possible codes: 'Hx' (homing completed, x=axis), 'A' (alarm state), 'W' (track is reverse-wound), and 'R...' (motor isRunning and position for each motor)

*/

#include <AccelStepper.h>

// Definition of the connected pins of the Arduino
#define enPinStage 2    // enable pin for the stage motor
#define dirPinStage 3   // direction pin for the stage motor
#define stepPinStage 4  // step pin for the stage motor

#define enPinTrack 5    // enable pin for the track motor
#define dirPinTrack 6   // direction pin for the track motor
#define stepPinTrack 7  // step pin for the track motor

#define enPinNod 8      // enable pin for the nod motor
#define dirPinNod 9     // direction pin for the nod motor
#define stepPinNod 10   // step pin for the nod motor

#define stageLimitPin 14
#define trackBottomLimitPin 25  // limit switch with a white wire
#define trackTopLimitPin 23  // limit switch with a red wire
#define nodForwardLimitPin  24  // limit switch with a blue wire
#define nodBackLimitPin 22  // limit switch with a green wire
#define estopPin 53 // physical red emergency stop button

#define stageMicrosteps 16
#define trackMicrosteps 4
#define nodMicrosteps 64

struct LimitSwitch {
  public:
    char id[5];
    int backoff;
    int direction;
    int axis;
    AccelStepper* motor;
    int pin;
};

AccelStepper stageMotor(AccelStepper::DRIVER, stepPinStage, dirPinStage);
AccelStepper trackMotor(AccelStepper::DRIVER, stepPinTrack, dirPinTrack);
AccelStepper nodMotor(AccelStepper::DRIVER, stepPinNod, dirPinNod);

LimitSwitch trackTopLimitSwitch = {"TTLS", 50 * trackMicrosteps, 1, 1, &trackMotor, trackTopLimitPin};
LimitSwitch trackBottomLimitSwitch = {"TBLS", 50 * trackMicrosteps, -1, 1, &trackMotor, trackBottomLimitPin};
LimitSwitch nodForwardLimitSwitch = {"NFLS", 10 * nodMicrosteps, 1, 2, &nodMotor, nodForwardLimitPin};
LimitSwitch nodBackLimitSwitch = {"NBLS", 10 * nodMicrosteps, -1, 2, &nodMotor, nodBackLimitPin};

// Variables for reading in serial commands
const int MAX_DIGITS = 10;
uint8_t incomingBytes[MAX_DIGITS + 3];
int incomingByte; 
int byteCounter = 0;

// Variables to keep track of machine states
float lastNonzeroTrackMotorSpeed = 0;
int homing[3] = {0, 0, 0};
bool needs_homing[3] = {1, 1, 1};

void checkAndHandleLimitSwitch(LimitSwitch& ls) {
  if (digitalRead(ls.pin) && digitalRead(ls.pin) && digitalRead(ls.pin)) {
    long hit_position = ls.motor->currentPosition();
    // Stop the motor immediately and set the position and speed to zero
    ls.motor->setCurrentPosition(0);

    // Ensure the track isn't reverse-wound
    if ((ls.pin == trackTopLimitPin && lastNonzeroTrackMotorSpeed < 0) || (ls.pin == trackBottomLimitPin && lastNonzeroTrackMotorSpeed > 0)) {
      Serial.print("W "); // Communicate that the top switch was hit from the wrong direction
      Serial.println(ls.id);
      homing[1] = 0;
      needs_homing[1] = 1;
      ls.motor->move(ls.direction * ls.backoff);
      ls.motor->runToPosition();
      return;
    }

    // Back off of the limit switch so it's no longer pressed
    ls.motor->move(-1 * ls.direction * ls.backoff);
    ls.motor->runToPosition();

    if (homing[ls.axis] == 1 && ls.direction == -1) {
      homing[ls.axis] = 0;
      needs_homing[ls.axis] = 0;

      // Communicate that homing has completed for this axis
      Serial.print("H "); 
      Serial.println(ls.axis);
    } else {
      needs_homing[ls.axis] = 1;
      Serial.print("L ");
      Serial.print(ls.id);
      Serial.print(" ");
      Serial.println(hit_position);
    }
  }
}

void setup() {
  Serial.begin(115200);

  // Enable all the motors
  stageMotor.setMaxSpeed(250 * stageMicrosteps); // Max value is 4000 (microcontroller limitation)
  stageMotor.setAcceleration(200.0 * stageMicrosteps);
  stageMotor.setEnablePin(enPinStage);
  stageMotor.enableOutputs();

  trackMotor.setMaxSpeed(1000 * trackMicrosteps); // Max value is 4000 (microcontroller limitation)
  trackMotor.setAcceleration(500.0 * trackMicrosteps);
  trackMotor.setPinsInverted(true, false, false);
  trackMotor.setEnablePin(enPinTrack);
  trackMotor.enableOutputs();

  nodMotor.setMaxSpeed(62.5 * nodMicrosteps); // Max value is 4000 (microcontroller limitation)
  nodMotor.setAcceleration(50.0 * nodMicrosteps);
  nodMotor.setPinsInverted(true, false, false);
  nodMotor.setEnablePin(enPinNod);
  nodMotor.enableOutputs();

  pinMode(stageLimitPin, INPUT_PULLUP);  
  pinMode(trackBottomLimitPin, INPUT_PULLUP);  
  pinMode(trackTopLimitPin, INPUT_PULLUP);  
  pinMode(nodBackLimitPin, INPUT_PULLUP);  
  pinMode(nodForwardLimitPin, INPUT_PULLUP);
  pinMode(estopPin, INPUT_PULLUP);  
}

void loop() {
  // Check if Emergency Stop is pressed
  if (digitalRead(estopPin)) {
    Serial.println("E");
    stageMotor.setCurrentPosition(0);
    trackMotor.setCurrentPosition(0);
    nodMotor.setCurrentPosition(0);
    bool needs_homing[3] = {1, 1, 1};
    delay(50);
    return;
  }

  // Read incoming command
  while (Serial.available() > 0) {
    incomingByte = Serial.read();
    incomingBytes[byteCounter] = incomingByte;
    byteCounter += 1;

    if (incomingByte == '\n') {
      // Convert the axis char to an int
      int axis = incomingBytes[1] - '0';

      // UNCOMMENT THIS ONCE THIS CODE IS FINALIZED
      // if ((incomingBytes[0] == 'M' || incomingBytes[0] == 'J') && needs_homing[axis] == 1) {
      //   Serial.println("N");
      //   continue; 
      // }

      // Convert the value at the end of the command to an int
      long value = 0;
      for (int i = 3; i < byteCounter - 1; i++){
        value = value*10 + incomingBytes[i] - '0';
      }
      if (incomingBytes[2] == '-') {
        value = -1 * value;
      }

      // Determine which motor will be affected
      AccelStepper* motor = NULL;
      switch (axis) {
        case 0:
          motor = &stageMotor;
          break;
        case 1:
          motor = &trackMotor;
          break;
        case 2:
          motor = &nodMotor;
          break;
      }

      switch (incomingBytes[0]) {
        case 'M': // Move to position
          motor->moveTo(value);
          break;
        case 'J': // Jog
          motor->move(value);
          break;
        case 'S': // Set speed
          motor->setMaxSpeed(value); 
          break;
        case 'A': // Set acceleration
          motor->setAcceleration(value);
          break;
        case 'H': // Home axis
          homing[axis] = 1;
          motor->move(-1000000);
          break;
        case 'F': // Force move, ignore limit switches
          motor->move(value);
          motor->runToPosition();
          break;
        case 'E': // Stop all motors
          motor->stop();
          homing[axis] = 0;
        case 'P': // Send motor isRunning and position data
          Serial.print("P");
          Serial.print(" ");
          Serial.print(stageMotor.isRunning());
          Serial.print(" ");
          Serial.print(stageMotor.currentPosition());
          Serial.print(" ");
          Serial.print(trackMotor.isRunning());
          Serial.print(" ");
          Serial.print(trackMotor.currentPosition());
          Serial.print(" ");
          Serial.print(nodMotor.isRunning());
          Serial.print(" ");
          Serial.println(nodMotor.currentPosition());
          break;
        case 'R': // Send maxSpeed and acceleration for each motor
          Serial.print("R");
          Serial.print(" ");
          Serial.print(stageMotor.maxSpeed());
          Serial.print(" ");
          Serial.print(stageMotor.acceleration());
          Serial.print(" ");
          Serial.print(trackMotor.maxSpeed());
          Serial.print(" ");
          Serial.print(trackMotor.acceleration());
          Serial.print(" ");
          Serial.print(nodMotor.maxSpeed());
          Serial.print(" ");
          Serial.println(nodMotor.acceleration());
          break;
      }

      byteCounter = 0;
      memset(incomingBytes, 0, sizeof(incomingBytes));
    }
  }

  stageMotor.run();
  trackMotor.run();
  nodMotor.run();

  float trackMotorSpeed = trackMotor.speed();

  // Check for limit switch presses on the carriage
  checkAndHandleLimitSwitch(trackTopLimitSwitch);
  checkAndHandleLimitSwitch(trackBottomLimitSwitch);
  checkAndHandleLimitSwitch(nodForwardLimitSwitch);
  checkAndHandleLimitSwitch(nodBackLimitSwitch);

  // Check stage limit switch separately
  if (digitalRead(stageLimitPin) && digitalRead(stageLimitPin) && digitalRead(stageLimitPin)) {
    if (homing[0] == 1) {
      stageMotor.move(100);

      Serial.println("L SOLS");

      stageMotor.runToPosition();
      stageMotor.setCurrentPosition(0);
      homing[0] = 0;
      needs_homing[0] = 0;

      Serial.println("H 0");
    }
  }

  // Update last nonzero track motor speed
  if (trackMotorSpeed != 0) {
    lastNonzeroTrackMotorSpeed = trackMotorSpeed;
  }
}

 #include <Wire.h>

#define IDLE   -1
#define CMD_ERROR -2

#define DEBUG_SERIAL  // comment out to suppress all debug Serial prints

// ===========================
// I2C DEFINITIONS
// ===========================
#define SLAVE_ADDR 0x55


// ===========================
// PIN DEFINITIONS
// ===========================
#define ARM_STEP_PIN 4
#define ARM_DIR_PIN 2

#define MUT_STEP_PIN 25
#define MUT_DIR_PIN 26


#define ARM_ENCODER_A_PIN 19 //13 = external, 19 = internal
#define ARM_ENCODER_B_PIN 18 //12 = external, 18 = internal 

#define MUT_ENCODER_A_PIN 32
#define MUT_ENCODER_B_PIN 33


#define ALERT_INTERRUPT_PIN 5
#define COLLISION_SWITCHES_PIN 15 //collision
#define ARM_HOME_PIN 34 //?
#define MUT_HOME_PIN 35



// ===========================
// ENCODER SETTINGS
// ===========================
#define ARM_ENCODER_COUNTS  (4000.0) // quadrature counts per revolution
#define MUT_ENCODER_COUNTS  (4000.0) // same encoder on MUT motor
#define MUT_HOME_OFFSET_COUNTS (1000) // encoder counts from home switch to MUT zero reference


// ===========================
// STATUS REPORTING VARIABLES
// ===========================

#define COLLISION 0
#define ARM_POS_REACHED 1
#define MUT_POS_REACHED 2

uint8_t systemStatus = 0; // register for holding status alerts
                          // bit0 -> collision error
                          // bit1 -> arm position reached 
                          // bit2 -> mut position reached
bool armHasReportedArrival = false;
bool mutHasReportedArrival = false;




// ===========================
// ENCODER VARIABLES
// ===========================
#define GEAR_RATIO (8.55) //8.55 or 1

enum motors {
  ARM_MOTOR = 1,
  MUT_MOTOR
};

volatile long armEncoderPosition = 0;
volatile long mutEncoderPosition = 0;

volatile bool armLastA = 0;
volatile bool armLastB = 0;
volatile bool mutLastA = 0;
volatile bool mutLastB = 0;


long getARMEncoderPosition() {
    noInterrupts();
    long pos = armEncoderPosition;
    interrupts();
    return pos;
}

long getMUTEncoderPosition() {
    noInterrupts();
    long pos = mutEncoderPosition;
    interrupts();
    return pos;
}



// ===========================
// I2C VARIABLES
// ===========================
enum commands {
  MOVE_MOTOR_ABS = 1,
  SET_HOME,
  START_HOMING_SEQ,
  HALT
};

union PositionUnion {
  float value;
  uint8_t bytes[4];
};

volatile PositionUnion posUnion;

volatile int command;
volatile int motorNum;
volatile float position;


int currentMotor = -1;
int commandStatus = 0;


// ===========================
// PID PARAMETERS
// ===========================
float armKp = 1.2;
float armKi = 0.0;
float armKd = 0.05;

float armIntegral = 0;
float armLastError = 0;
//-----
float mutKp = 1.2;
float mutKi = 0.0;
float mutKd = 0.05;

float mutIntegral = 0;
float mutLastError = 0;


// ===========================
// CONTROL VARIABLES
// ===========================
long armTargetPositionCounts = 0;
long mutTargetPositionCounts = 0;

unsigned long lastControlTime = 0;
const int controlIntervalMicros = 1000; // 1 kHz loop

long armCurrentPos = 0;
long mutCurrentPos = 0;

// Stepper timing
unsigned long armLastStepTime = 0;
unsigned long mutLastStepTime = 0;

// Maximum speed in steps/sec
int maxStepRate = 800;

// ===========================
// COLLISION ISR
// ===========================
void collision_ISR(){
  reportEvent(COLLISION);
  // for(;;){} //hang if error is detected, prob not good practice to have in ISR
}


// volatile bool homing = false;
volatile bool armHoming = false;
volatile bool mutHoming = false;

// ===========================
// HOMING ISRs
// ===========================
void arm_homing_ISR(){
  if(armHoming){
    armEncoderPosition = 0;
    armTargetPositionCounts = 0;
    armHoming = false;
  }
  // else reportEvent(COLLISION);
}

void mut_homing_ISR(){
  if(mutHoming){
    mutEncoderPosition = MUT_HOME_OFFSET_COUNTS;
    mutTargetPositionCounts = MUT_HOME_OFFSET_COUNTS;
    mutHoming = false;
  }
  // else reportEvent(COLLISION);
}


// ===========================
// ENCODER ISRS
// ===========================
void IRAM_ATTR arm_ISR_encoder() {
    bool A = digitalRead(ARM_ENCODER_A_PIN);
    bool B = digitalRead(ARM_ENCODER_B_PIN);

    if (A != armLastA) {
        if (A == B) armEncoderPosition++; // CW
        else armEncoderPosition--;        // CCW
    }

    if (B != armLastB) {
        if (A != B) armEncoderPosition++; // CW
        else armEncoderPosition--;        // CCW
    }

    armLastA = A;
    armLastB = B;
}

void IRAM_ATTR mut_ISR_encoder() {
    bool A = digitalRead(MUT_ENCODER_A_PIN);
    bool B = digitalRead(MUT_ENCODER_B_PIN);

    if (A != mutLastA) {
        if (A == B) mutEncoderPosition++; // CW
        else mutEncoderPosition--;        // CCW
    }

    if (B != mutLastB) {
        if (A != B) mutEncoderPosition++; // CW
        else mutEncoderPosition--;        // CCW
    }

    mutLastA = A;
    mutLastB = B;
}


// ===========================
// I2C ISR
// ===========================
void receiveEvent(int howMany) {
  int useless = Wire.read(); //gives address but dont need it 
  command = Wire.read();
  motorNum = Wire.read();
  for (int i = 0; i < 4; i++) {
    posUnion.bytes[i] = Wire.read(); //reads float
  }

  position = posUnion.value;

#ifdef DEBUG_SERIAL
  Serial.println(command);
  Serial.println(motorNum);
  Serial.println(position);
#endif
}


void requestEvent() {
    uint8_t snapshot = systemStatus;
    Wire.write(snapshot);
    systemStatus &= ~snapshot; // clear only the bits that were just sent
    if (systemStatus == 0) {
        digitalWrite(ALERT_INTERRUPT_PIN, LOW);
    }
}

// ===========================
// I2C FUNCTIONS
// ===========================
int commandHandler(){
  switch (command){
    case MOVE_MOTOR_ABS: 
      if(motorNum != ARM_MOTOR && motorNum != MUT_MOTOR) return CMD_ERROR;
      switch (motorNum) {
        case ARM_MOTOR:
          moveToPosition(position * GEAR_RATIO, ARM_MOTOR);
          armCurrentPos = position;
          break;
        case MUT_MOTOR:
          moveToPosition(position, MUT_MOTOR);
          mutCurrentPos = position;
          break;
      }
      

      command = IDLE; motorNum = IDLE;
      
      return MOVE_MOTOR_ABS;
    case SET_HOME:
      switch(motorNum){
        case ARM_MOTOR:
          armEncoderPosition = 0;
          armTargetPositionCounts = 0;
          break;
        case MUT_MOTOR:
          mutEncoderPosition = 0;
          mutTargetPositionCounts = 0;
          break;
      }
      
      armHoming = false;
      mutHoming = false;
      command = IDLE; motorNum = IDLE;

      return SET_HOME;
    case START_HOMING_SEQ:
      armHoming = true; // do NOT set mutHoming here — prevents premature MUT ISR trigger
      moveToPosition(GEAR_RATIO * -360, ARM_MOTOR);
      while(armHoming){
        updatePID();
      }
      lastControlTime = micros(); // resync timer after blocking loop

      mutHoming = true;
      moveToPosition(360, MUT_MOTOR);
      while(mutHoming){
        updatePID();
      }
      lastControlTime = micros(); // resync timer after blocking loop

      command = IDLE; motorNum = IDLE;
      return START_HOMING_SEQ;
    case HALT:
      //disable motors, not implemented
      return HALT;
    default:
      return -2;
  }
}


// ===========================
// STEPPER CONTROL
// ===========================
// void stepMotor(int direction, int motorNum) {
//     switch (motorNum){
//       case ARM_MOTOR:
//         digitalWrite(ARM_DIR_PIN, direction > 0 ? HIGH : LOW);
//         digitalWrite(ARM_STEP_PIN, HIGH);
//         delayMicroseconds(2);
//         digitalWrite(ARM_STEP_PIN, LOW);
//         delayMicroseconds(2);
//         break;
//       case MUT_MOTOR:
//         digitalWrite(MUT_DIR_PIN, direction > 0 ? HIGH : LOW);
//         digitalWrite(MUT_STEP_PIN, HIGH);
//         delayMicroseconds(2);
//         digitalWrite(MUT_STEP_PIN, LOW);
//         delayMicroseconds(2);
//         break;
//     }
// }



void stepARMMotor(int direction){
  digitalWrite(ARM_DIR_PIN, direction > 0 ? HIGH : LOW);
  digitalWrite(ARM_STEP_PIN, HIGH);
  delayMicroseconds(2);
  digitalWrite(ARM_STEP_PIN, LOW);
  delayMicroseconds(2);
}

void stepMUTMotor(int direction){
  digitalWrite(MUT_DIR_PIN, direction > 0 ? LOW : HIGH);
  digitalWrite(MUT_STEP_PIN, HIGH);
  delayMicroseconds(2);
  digitalWrite(MUT_STEP_PIN, LOW);
  delayMicroseconds(2);
}


// ===========================
// PID LOOP
// ===========================
void updatePID() {
    long armCurrentPos = getARMEncoderPosition();
    long armError = armTargetPositionCounts - armCurrentPos;

    long mutCurrentPos = getMUTEncoderPosition();
    long mutError = mutTargetPositionCounts - mutCurrentPos;

    armIntegral += armError * (controlIntervalMicros / 1e6);
    float armDerivative = (armError - armLastError) / (controlIntervalMicros / 1e6);
    armLastError = armError;

    mutIntegral += mutError * (controlIntervalMicros / 1e6);
    float mutDerivative = (mutError - mutLastError) / (controlIntervalMicros / 1e6);
    mutLastError = mutError;

    float armOutput = armKp * armError + armKi * armIntegral + armKd * armDerivative;
    float mutOutput = mutKp * mutError + mutKi * mutIntegral + mutKd * mutDerivative;

    // Clamp speed
    if (armOutput > maxStepRate)  armOutput = maxStepRate;
    if (armOutput < -maxStepRate) armOutput = -maxStepRate;

    if (mutOutput > maxStepRate)  mutOutput = maxStepRate;
    if (mutOutput < -maxStepRate) mutOutput = -maxStepRate;

    // Convert to step interval
    if (armOutput != 0) {
        unsigned long stepInterval = 1000000.0 / abs(armOutput); // microseconds per step
        unsigned long now = micros();
        if (now - armLastStepTime >= stepInterval) {
            armLastStepTime = now;
            int direction = (armOutput > 0) ? 1 : -1;
            stepARMMotor(direction);
        }
    }

    if (mutOutput != 0) {
        unsigned long stepInterval = 1000000.0 / abs(mutOutput); // microseconds per step
        unsigned long now = micros();
        if (now - mutLastStepTime >= stepInterval) {
            mutLastStepTime = now;
            int direction = (mutOutput > 0) ? 1 : -1;
            stepMUTMotor(-direction);
        }
    }

#ifdef DEBUG_SERIAL
    // Debug print at 20 Hz
    static unsigned long lastDebug = 0;
    if (millis() - lastDebug >= 50) {
        lastDebug = millis();
        Serial.print("ARM Target=");
        Serial.print(armTargetPositionCounts);
        Serial.print(" ARM Pos=");
        Serial.print(armCurrentPos);
        Serial.print(" ARM Err=");
        Serial.println(armError);
        Serial.print("armHasReportedArrival: ");
        Serial.println(armHasReportedArrival);

        Serial.print("MUT Target=");
        Serial.print(mutTargetPositionCounts);
        Serial.print(" MUT Pos=");
        Serial.print(mutCurrentPos);
        Serial.print(" MUT Err=");
        Serial.println(mutError);
        Serial.print("mutHasReportedArrival: ");
        Serial.println(mutHasReportedArrival);
        Serial.print("armHoming: ");
        Serial.println(armHoming);
        Serial.print("mutHoming: ");
        Serial.println(mutHoming);
        Serial.println("------------------------------------");
    }
#endif
}


// ===========================
// MOVE FUNCTION
// ===========================
void moveToPosition(float degrees, int motorNum) {
    switch (motorNum){
      case ARM_MOTOR:
        if(!armHoming && degrees > 80) degrees = 80; // clamp degrees, not global position
        armTargetPositionCounts = (long)(degrees * (ARM_ENCODER_COUNTS / 360.0));
        armHasReportedArrival = false; // only reset the flag for the motor being moved
        break;
      case MUT_MOTOR:
        mutTargetPositionCounts = (long)(degrees * (4000.0 / 360.0));
        mutHasReportedArrival = false; // only reset the flag for the motor being moved
        break;
    }
#ifdef DEBUG_SERIAL
    Serial.print("motorNum: ");
    Serial.print(motorNum);
    Serial.print(" MoveTo: ");
    Serial.print(degrees);
    Serial.print(" arm deg -> ");
    Serial.print(armTargetPositionCounts);
    Serial.println(" counts");
    Serial.print(" mut deg -> ");
    Serial.print(mutTargetPositionCounts);
    Serial.println(" counts");
#endif
}


// ===========================
// CHECK IF POSITION REACHED
// ===========================
bool positionReached(long toleranceCounts = 5, int motorNum = 0) {
    long err = LONG_MAX; // safe default — not reached if motorNum unknown
    switch (motorNum) {
      case ARM_MOTOR:
        err = abs(armTargetPositionCounts - getARMEncoderPosition());
        break;
      case MUT_MOTOR:
        err = abs(mutTargetPositionCounts - getMUTEncoderPosition());
        break;
      default:
        return false;
    }
    return (err <= toleranceCounts);
}

void reportEvent(uint8_t bitIndex) {
    systemStatus |= (1 << bitIndex); // Set the specific bit
    digitalWrite(ALERT_INTERRUPT_PIN, HIGH); // Alert the Pi
}


// ===========================
// SETUP
// ===========================
void setup() {
    Wire.begin(SLAVE_ADDR);
    Wire.onReceive(receiveEvent);
    Wire.onRequest(requestEvent);

    Serial.begin(115200);
    { unsigned long _t = millis(); while(!Serial && millis()-_t < 3000); } // 3s timeout

    pinMode(ARM_STEP_PIN, OUTPUT);
    pinMode(ARM_DIR_PIN, OUTPUT);
    pinMode(ARM_ENCODER_A_PIN, INPUT_PULLUP);
    pinMode(ARM_ENCODER_B_PIN, INPUT_PULLUP);

    pinMode(MUT_STEP_PIN, OUTPUT);
    pinMode(MUT_DIR_PIN, OUTPUT);
    pinMode(MUT_ENCODER_A_PIN, INPUT_PULLUP);
    pinMode(MUT_ENCODER_B_PIN, INPUT_PULLUP);

    pinMode(ALERT_INTERRUPT_PIN, OUTPUT);

    pinMode(COLLISION_SWITCHES_PIN, INPUT_PULLUP); //INPUT??

    pinMode(ARM_HOME_PIN, INPUT); //INPUT??
    pinMode(MUT_HOME_PIN, INPUT); //INPUT??



    digitalWrite(ALERT_INTERRUPT_PIN, LOW);

    attachInterrupt(digitalPinToInterrupt(ARM_ENCODER_A_PIN), arm_ISR_encoder, CHANGE);
    attachInterrupt(digitalPinToInterrupt(ARM_ENCODER_B_PIN), arm_ISR_encoder, CHANGE);

    attachInterrupt(digitalPinToInterrupt(MUT_ENCODER_A_PIN), mut_ISR_encoder, CHANGE);
    attachInterrupt(digitalPinToInterrupt(MUT_ENCODER_B_PIN), mut_ISR_encoder, CHANGE);

    attachInterrupt(digitalPinToInterrupt(ARM_HOME_PIN), arm_homing_ISR, HIGH);
    attachInterrupt(digitalPinToInterrupt(MUT_HOME_PIN), mut_homing_ISR, HIGH); 


    armLastA = digitalRead(ARM_ENCODER_A_PIN);
    armLastB = digitalRead(ARM_ENCODER_B_PIN);

    mutLastA = digitalRead(MUT_ENCODER_A_PIN);
    mutLastB = digitalRead(MUT_ENCODER_B_PIN);

    Serial.println("Stepper PID Controller Ready");
    lastControlTime = micros(); // ensure first PID tick isn't overdue
}


// ===========================
// MAIN LOOP
// ===========================
void loop() {
    // PID update + position-reached check at 1 kHz
    unsigned long now = micros();
    if (now - lastControlTime >= controlIntervalMicros) {
        lastControlTime = now;
        updatePID();

        // Position-reached logic runs inside the 1 kHz block to avoid
        // firing hundreds of thousands of times per second
        if (!armHasReportedArrival && positionReached(5, ARM_MOTOR)) {
#ifdef DEBUG_SERIAL
            Serial.println("ARM POSITION REACHED");
#endif
            reportEvent(ARM_POS_REACHED);
            armHasReportedArrival = true;
        }
        if (!mutHasReportedArrival && positionReached(5, MUT_MOTOR)) {
#ifdef DEBUG_SERIAL
            Serial.println("MUT POSITION REACHED");
#endif
            reportEvent(MUT_POS_REACHED);
            mutHasReportedArrival = true;
        }
    }


// COMMAND STATE MACHINE
  if(command != IDLE) {
    commandStatus = commandHandler();
    if (commandStatus == CMD_ERROR){ //add more error statements
#ifdef DEBUG_SERIAL
      Serial.println("COMMAND HANDLER ERROR");
#endif
      for(;;);
    }
    if(systemStatus == 1 << COLLISION){
#ifdef DEBUG_SERIAL
      Serial.println("COLLISION DETECTED. HALTING");
#endif
      for(;;); //implement enable pin to truly stop motors?
    }
  }


}

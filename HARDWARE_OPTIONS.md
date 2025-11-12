# Hardware Controller Options

The LEGO sorter needs to control:
- **Servos**: 10-20 servos for bin doors (via PCA9685 I2C boards)
- **DC Motors**: 4 motors for conveyors/hoppers (via L298N H-bridge)
- **Encoders**: Rotary encoder for position tracking
- **Break Beam Sensors**: IR sensors for piece detection (optional)

You have **two options** for the hardware controller:

## Option 1: Arduino (Current Implementation) ✅

### Hardware
- **Arduino Nano/Uno** ($5-25)
- Communicates via USB serial
- Runs Firmata protocol firmware

### Pros
- ✅ **Currently implemented** - Works out of the box
- ✅ **Simple** - Just upload firmware and plug in USB
- ✅ **Real-time** - Dedicated microcontroller, no OS jitter
- ✅ **Reliable** - Won't crash or hang from Python issues
- ✅ **Cheap** - Arduino Nano clones are $3-5
- ✅ **Low power** - Can run 24/7 without issues

### Cons
- ❌ **Requires firmware** - Need to compile and upload `.ino` file
- ❌ **Limited debugging** - Harder to troubleshoot hardware issues
- ❌ **Firmata overhead** - Custom protocol layer

### Setup Instructions

See [`setup.md`](./setup.md) for complete Arduino setup.

**Quick version:**
```bash
# 1. Install Arduino IDE or CLI
brew install arduino-ide

# 2. Open embedded/firmata/firmata.ino in Arduino IDE

# 3. Install Firmata library
# Tools > Manage Libraries > Search "Firmata" > Install

# 4. Set board and port
# Tools > Board > Arduino Nano
# Tools > Port > /dev/cu.usbmodem14201 (or your device)

# 5. Upload
# Sketch > Upload

# 6. Set environment variable
export MC_PATH="/dev/cu.usbmodem14201"

# 7. Run robot
./robot/run.sh -y
```

### Python Integration
Uses `pyFirmata` library:
```python
from robot.irl.our_arduino import OurArduinoNano

arduino = OurArduinoNano(gc, port="/dev/cu.usbmodem14201", command_delay_ms=8)
arduino.sysex(0x01, [0x07, pca9685_address])  # Initialize PCA9685
```

---

## Option 2: Raspberry Pi (Alternative) 🆕

### Hardware
- **Raspberry Pi 3/4/5** ($35-80)
- Controls GPIO pins directly
- No separate microcontroller needed

### Pros
- ✅ **Direct GPIO control** - No firmware needed
- ✅ **Better debugging** - Full Linux OS, SSH access
- ✅ **More processing power** - Can run vision system on same device
- ✅ **I2C built-in** - Native support for PCA9685 boards
- ✅ **Python-native** - Use RPi.GPIO or gpiozero libraries

### Cons
- ❌ **More expensive** - $35-80 vs $5-25
- ❌ **Not currently implemented** - Requires code adaptation
- ❌ **OS jitter** - Linux can introduce timing issues
- ❌ **More complex** - Full OS to maintain, more failure points
- ❌ **Higher power** - Needs proper power supply, can't run off USB

### Implementation Plan

To use Raspberry Pi, you need to:

1. **Create RPi hardware interface** (similar to `our_arduino.py`)
2. **Implement direct GPIO control** for DC motors
3. **Use I2C library** for PCA9685 servo control
4. **Handle encoder reading** via GPIO interrupts
5. **Update config** to use RPi instead of Arduino

### Setup Instructions

#### 1. Install Dependencies

```bash
# On Raspberry Pi
sudo apt-get update
sudo apt-get install -y python3-pip python3-dev i2c-tools

# Enable I2C
sudo raspi-config
# Interface Options > I2C > Enable

# Python libraries
pip3 install RPi.GPIO
pip3 install adafruit-circuitpython-pca9685
pip3 install adafruit-circuitpython-motor
```

#### 2. Wire Connections

**PCA9685 Servo Driver:**
- VCC → 5V
- GND → GND
- SDA → GPIO 2 (Pin 3)
- SCL → GPIO 3 (Pin 5)

**DC Motor Driver (L298N):**
- IN1 → GPIO 17 (Pin 11)
- IN2 → GPIO 27 (Pin 13)
- ENA → GPIO 22 (Pin 15) - PWM for speed control

Repeat for each motor using different GPIO pins.

**Rotary Encoder:**
- CLK → GPIO 23 (Pin 16)
- DT → GPIO 24 (Pin 18)
- GND → GND

#### 3. Create Raspberry Pi Hardware Module

Create `robot/irl/raspberry_pi.py`:

```python
import time
import board
import busio
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo
import RPi.GPIO as GPIO
from typing import Dict, List
from robot.global_config import GlobalConfig

class RaspberryPiController:
    """Raspberry Pi GPIO controller for LEGO sorter"""

    def __init__(self, gc: GlobalConfig):
        self.gc = gc

        # Initialize I2C for PCA9685
        i2c = busio.I2C(board.SCL, board.SDA)
        self.pca = PCA9685(i2c)
        self.pca.frequency = 50  # 50Hz for servos

        # Initialize GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Motor pins (example for one motor)
        self.motor_pins = {
            'main_conveyor': {'in1': 17, 'in2': 27, 'ena': 22},
            'feeder_conveyor': {'in1': 5, 'in2': 6, 'ena': 13},
        }

        # Setup motor pins
        for motor, pins in self.motor_pins.items():
            GPIO.setup(pins['in1'], GPIO.OUT)
            GPIO.setup(pins['in2'], GPIO.OUT)
            GPIO.setup(pins['ena'], GPIO.OUT)
            # PWM on enable pin
            pins['pwm'] = GPIO.PWM(pins['ena'], 1000)  # 1kHz
            pins['pwm'].start(0)

    def set_servo_angle(self, channel: int, angle: int):
        """Set servo angle on PCA9685 channel"""
        # Map angle (0-180) to pulse width (1000-2000 microseconds)
        pulse_width = int(1000 + (angle / 180.0 * 1000))
        self.pca.channels[channel].duty_cycle = int(pulse_width / 1000000 * 0xFFFF)

    def set_motor_speed(self, motor_name: str, speed: int):
        """Set DC motor speed (-255 to 255)"""
        pins = self.motor_pins[motor_name]

        if speed > 0:
            GPIO.output(pins['in1'], GPIO.HIGH)
            GPIO.output(pins['in2'], GPIO.LOW)
        elif speed < 0:
            GPIO.output(pins['in1'], GPIO.LOW)
            GPIO.output(pins['in2'], GPIO.HIGH)
        else:
            GPIO.output(pins['in1'], GPIO.LOW)
            GPIO.output(pins['in2'], GPIO.LOW)

        duty_cycle = min(100, abs(speed) / 255.0 * 100)
        pins['pwm'].ChangeDutyCycle(duty_cycle)

    def cleanup(self):
        """Clean up GPIO"""
        for motor, pins in self.motor_pins.items():
            pins['pwm'].stop()
        GPIO.cleanup()
```

#### 4. Adapt Existing Classes

Create wrappers that match the Arduino interface:

```python
# robot/irl/rpi_motors.py

class RPiServo:
    """Servo control via Raspberry Pi"""

    def __init__(self, gc, channel, rpi_controller):
        self.gc = gc
        self.channel = channel
        self.rpi = rpi_controller

    def setAngle(self, angle: int, duration=None):
        if duration:
            # Gradual movement
            # Implement smooth transitions
            pass
        else:
            self.rpi.set_servo_angle(self.channel, angle)

class RPiDCMotor:
    """DC Motor control via Raspberry Pi"""

    def __init__(self, gc, rpi_controller, motor_name):
        self.gc = gc
        self.rpi = rpi_controller
        self.motor_name = motor_name

    def setSpeed(self, speed: int, override=False):
        self.rpi.set_motor_speed(self.motor_name, speed)
```

#### 5. Update Config

Modify `robot/irl/config.py`:

```python
def buildIRLSystemInterface(config, gc):
    # Check if using Raspberry Pi
    use_rpi = os.getenv("USE_RPI", "false").lower() == "true"

    if use_rpi:
        from robot.irl.raspberry_pi import RaspberryPiController
        from robot.irl.rpi_motors import RPiServo, RPiDCMotor, RPiPCA9685

        rpi = RaspberryPiController(gc)

        # Create servo controllers
        # ... build distribution modules with RPiServo

        return {
            "arduino": None,  # No Arduino when using RPi
            "rpi_controller": rpi,
            # ... rest of interface
        }
    else:
        # Existing Arduino code
        # ...
```

#### 6. Run with Raspberry Pi

```bash
# Set environment variable
export USE_RPI=true

# Run normally (no MC_PATH needed)
./robot/run.sh -y
```

### Testing on Raspberry Pi

```bash
# Test I2C detection
i2cdetect -y 1
# Should show PCA9685 at address 0x40

# Test GPIO
python3 -c "import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM); print('GPIO OK')"

# Test servo (move channel 0 to 90 degrees)
python3 << EOF
import board
import busio
from adafruit_pca9685 import PCA9685

i2c = busio.I2C(board.SCL, board.SDA)
pca = PCA9685(i2c)
pca.frequency = 50

# Set servo to middle position
pca.channels[0].duty_cycle = 0x1000 * 1.5  # ~90 degrees
print("Servo moved to 90 degrees")
EOF
```

---

## Comparison Table

| Feature | Arduino | Raspberry Pi |
|---------|---------|--------------|
| **Cost** | $5-25 | $35-80 |
| **Setup Complexity** | Medium (firmware) | Low (Python only) |
| **Real-time Control** | Excellent | Good (OS jitter) |
| **Processing Power** | Low | High |
| **GPIO Pins** | ~20 | 40 |
| **Python Integration** | Via Firmata | Direct |
| **Debugging** | Hard | Easy (SSH, logs) |
| **Power Draw** | ~100mA | ~500-900mA |
| **Status** | ✅ Implemented | ⚠️ Needs implementation |

## Recommendation

**For most users: Use Arduino**
- Current implementation works
- Cheaper and simpler
- More reliable for 24/7 operation
- Real-time guarantees

**Consider Raspberry Pi if:**
- You want to run vision system on same device
- You need easier debugging and development
- You're comfortable with Linux/GPIO programming
- You want to avoid firmware compilation

## Hybrid Option (Best of Both Worlds)

Run **Python on Raspberry Pi** + **Arduino for GPIO control**:

```
Raspberry Pi 4 (Vision + Python + FastAPI)
    |
    USB
    |
Arduino Nano (GPIO/Motors/Servos)
```

This gives you:
- ✅ Powerful vision processing on Pi
- ✅ Reliable real-time control on Arduino
- ✅ No OS jitter for critical timing
- ✅ Easy development via SSH to Pi
- ✅ Currently implemented setup

This is actually the **recommended architecture** if you have both devices!

## Can I Mix Arduino and Raspberry Pi?

**Yes!** You can run the entire Python system on a Raspberry Pi while using Arduino for hardware control:

```bash
# On Raspberry Pi
export MC_PATH="/dev/ttyUSB0"  # Arduino connected via USB
export REBRICKABLE_API_KEY="your_key"

./robot/run.sh -y
```

Benefits:
- Pi handles: Vision, AI, web server, database
- Arduino handles: Motors, servos, sensors
- Best of both worlds!

---

## Implementation Status

### ✅ Arduino (Ready Now)
- Fully implemented
- Tested and working
- See `setup.md` for instructions

### ⚠️ Raspberry Pi GPIO (Needs Implementation)
- Would require ~200-300 lines of code
- Estimated time: 4-6 hours
- Architecture is clear, just needs coding

If you want to use Raspberry Pi GPIO directly (no Arduino), let me know and I can implement the RPi hardware interface!

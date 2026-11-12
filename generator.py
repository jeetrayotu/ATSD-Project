"""
Robot Code Generator
--------------------
Reads an IML JSON model and generates Arduino C++ sketches

Usage:
    python generator.py <model.json> [output_directory]
"""

import json
import os
import re
import sys
from pathlib import Path

def to_constant(value):
    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, str):
        return '"' + value.replace('"', '\\"') + '"'

    return str(value)

def safe_name(name):
    name = re.sub(r"\W+", "_", str(name))
    name = re.sub(r"^[^a-zA-Z_]+", "", name)

    return name or "unnamed"

def get_value(obj, *keys, default=None):
    if not isinstance(obj, dict):
        return default
    for key in keys:
        if key in obj:
            return obj[key]

    return default

# ---------------------------------------------------------
# Model loading
# ---------------------------------------------------------

class RobotCodeGenerator:
    def __init__(self, model_path, output_directory):
        self.model_path = Path(model_path)
        self.output_directory = Path(output_directory)

        self.model = {}
        self.generated_files = []

    def get_class(self, obj):
        class_id = obj.get("classId")
        meta_classes = self.model.get("metaModel", {}).get("classes", [])

        for cls in meta_classes:
            if cls.get("id") == class_id:
                return cls.get("name", "")

        return get_value(
            obj,
            "class",
            "className",
            "type",
            "classifier",
            default=""
        )

    def get_attributes(self, obj):
        raw_attributes = get_value(
            obj,
            "attributeValues",
            "attributes",
            "properties",
            "values",
            default={}
        )

        if isinstance(raw_attributes, list):
            result = {}

            for attribute in raw_attributes:
                if isinstance(attribute, dict):
                    name = get_value(attribute, "name", "attribute", "key")
                    value = get_value(attribute, "value", "defaultValue")
                    if name is not None:
                        result[name] = value
            return result

        if not isinstance(raw_attributes, dict):
            return {}

        class_id = obj.get("classId")
        meta_classes = self.model.get("metaModel", {}).get("classes", [])
        attr_id_to_name = {}

        for cls in meta_classes:
            if cls.get("id") == class_id:
                for attr in cls.get("attributes", []):
                    attr_id_to_name[attr.get("id")] = attr.get("name")
                break
        resolved = {}

        for key, value in raw_attributes.items():
            name = attr_id_to_name.get(key, key)
            resolved[name] = value
        return resolved

    def load_model(self):
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model file not found: {self.model_path}"
            )
        
        with open(self.model_path, "r", encoding="utf-8") as file:
            self.model = json.load(file)

        print(f"Loaded model: {self.model_path}")

# -----------------------------------------------------
# Instance model extraction
# -----------------------------------------------------

    def get_instance_models(self):
        models = self.model.get("instanceModels", [])

        if isinstance(models, dict):
            return list(models.values())

        return models

    def get_model_name(self, model):
        return get_value(
            model,
            "name",
            "modelName",
            "title",
            default="UnnamedModel"
        )

    def get_model_objects(self, model):
        objects = get_value(
            model,
            "objects",
            "elements",
            "nodes",
            "instances",
            default=[]
        )

        if isinstance(objects, dict):
            return list(objects.values())
        return objects

    def find_objects(self, model, class_name):
        return [
            obj for obj in self.get_model_objects(model)
            if self.get_class(obj) == class_name
        ]

    def get_object_attributes(self, model, class_name):
        objects = self.find_objects(model, class_name)

        if not objects:
            return {}

        return self.get_attributes(objects[0])

# -----------------------------------------------------
# Model validation
# -----------------------------------------------------

    def validate_model(self, model):
        robot_objects = self.find_objects(model, "Robot")
        controller_objects = self.find_objects(
            model,
            "Controller"
        )

        if not robot_objects:
            return False

        if not controller_objects:
            return False

        robot_attributes = self.get_attributes(robot_objects[0])
        controller_attributes = self.get_attributes(
            controller_objects[0]
        )

        if not robot_attributes.get("name"):
            return False

        for key in (
            "cruiseSpeed",
            "turnSpeed",
            "defaultTurnAngle"
        ):
            if controller_attributes.get(key) is None:
                return False

        return True

# -----------------------------------------------------
# Code generation
# -----------------------------------------------------

    def generate_header(self, model_name):
        return f"""/*
 * Generated Arduino Robot Code
 *
 * Instance Model: {model_name}
 * Generated automatically by RobotCodeGenerator.
 */

#include <Arduino.h>
#include <FastLED.h>

"""

    def generate_constants(self, model):
        lines = []

        robot = self.find_objects(model, "Robot")[0]
        controller = self.find_objects(model, "Controller")[0]

        robot_attributes = self.get_attributes(robot)
        controller_attributes = self.get_attributes(controller)

        robot_name = robot_attributes.get("name", "Robot")

        lines.append("// Robot configuration")
        lines.append(
            f'const char* ROBOT_NAME = "{robot_name}";'
        )

        lines.append("\n// Controller configuration")

        for attribute in (
            "cruiseSpeed",
            "turnSpeed",
            "defaultTurnAngle"
        ):
            value = controller_attributes.get(attribute, 0)

            lines.append(
                f"const int CONTROLLER_{safe_name(attribute).upper()} "
                f"= {to_constant(value)};"
            )

        lines.append("")

        # Distance sensors
        for index, obj in enumerate(
            self.find_objects(model, "DistanceSensor")
        ):
            attrs = self.get_attributes(obj)
            prefix = f"DISTANCE_SENSOR_{index}"

            lines.append(f"// Distance sensor {index + 1}")

            lines.append(
                f"const int {prefix}_TRIG_PIN = "
                f"{attrs.get('trigPIN', 0)};"
            )

            lines.append(
                f"const int {prefix}_ECHO_PIN = "
                f"{attrs.get('echoPIN', 0)};"
            )

            lines.append(
                f"const int {prefix}_READ_INTERVAL_MS = "
                f"{attrs.get('readIntervalMs', 100)};"
            )

            lines.append(
                f'const char* {prefix}_MOUNTING = '
                f'"{attrs.get("mounting", "unknown")}";'
            )

            lines.append("")

        # Line tracker
        for index, obj in enumerate(
            self.find_objects(model, "LineTracker")
        ):
            attrs = self.get_attributes(obj)

            lines.append("// Line tracker")
            lines.append(
                f"const int LINE_TRACKER_{index}_THRESHOLD = "
                f"{attrs.get('darknessThreshold', 0)};"
            )

        lines.append("")

        # Status LED
        for index, obj in enumerate(
            self.find_objects(model, "StatusLED")
        ):
            attrs = self.get_attributes(obj)

            lines.append("// Status LED")
            lines.append(
                f"const int STATUS_LED_{index}_PIN = "
                f"{attrs.get('pin', 0)};"
            )

            lines.append(
                f"const int STATUS_LED_{index}_LED_COUNT = "
                f"{attrs.get('ledCount', 1)};"
            )

            lines.append(
                f"const int STATUS_LED_{index}_BLINK_INTERVAL = "
                f"{attrs.get('blinkIntervalMs', 250)};"
            )

        lines.append("")

        # Motors
        for index, obj in enumerate(
            self.find_objects(model, "Motor")
        ):
            attrs = self.get_attributes(obj)
            prefix = f"MOTOR_{index}"

            lines.append(f"// Motor {index + 1}")

            lines.append(
                f'const char* {prefix}_SIDE = '
                f'"{attrs.get("side", "unknown")}";'
            )

            lines.append(
                f"const int {prefix}_PWM_PIN = "
                f"{attrs.get('pwnPin', attrs.get('pwmPin', 0))};"
            )

            lines.append(
                f"const int {prefix}_DIRECTION_PIN = "
                f"{attrs.get('directionPin', 0)};"
            )

            lines.append("")

        # Motor driver
        drivers = self.find_objects(model, "MotorDriver")

        if drivers:
            attrs = self.get_attributes(drivers[0])

            lines.append("// Motor driver")

            lines.append(
                f"const int MOTOR_DRIVER_DEFAULT_SPEED = "
                f"{attrs.get('defaultSpeed', 0)};"
            )

            if attrs.get("standbyPin") is not None:
                lines.append(
                    f"const int MOTOR_DRIVER_STANDBY_PIN = "
                    f"{attrs['standbyPin']};"
                )

            lines.append("")

        return "\n".join(lines)

# -----------------------------------------------------
# Distance sensor functions
# -----------------------------------------------------

    def generate_distance_functions(self, model):
        lines = []
        sensors = self.find_objects(model, "DistanceSensor")

        for index, obj in enumerate(sensors):
            prefix = f"distance_sensor_{index}"

            lines.append(f"""
// Read distance from distance sensor {index + 1}
float {prefix}_read() {{

    digitalWrite(DISTANCE_SENSOR_{index}_TRIG_PIN, LOW);
    delayMicroseconds(2);

    digitalWrite(DISTANCE_SENSOR_{index}_TRIG_PIN, HIGH);
    delayMicroseconds(10);

    digitalWrite(DISTANCE_SENSOR_{index}_TRIG_PIN, LOW);

    long duration = pulseIn(
        DISTANCE_SENSOR_{index}_ECHO_PIN,
        HIGH,
        30000
    );

    if (duration == 0) {{
        return 0;
    }}

    float distance = duration * 0.0343 / 2.0;

    return distance;
}}
""")

        return "\n".join(lines)

# -----------------------------------------------------
# Line tracker functions
# -----------------------------------------------------

    def generate_line_functions(self, model):
        lines = []
        trackers = self.find_objects(model, "LineTracker")
        channels = self.find_objects(model, "LineChannel")

        if not trackers:
            return ""

        lines.append("// Line tracker functions")

        for index, channel in enumerate(channels):
            attrs = self.get_attributes(channel)

            position = safe_name(
                attrs.get("position", f"channel_{index}")
            ).lower()

            pin = attrs.get("pin", 0)

            lines.append(
                f"int line_tracker_read_{position}() {{"
            )

            lines.append(
                f"    return analogRead({pin});"
            )

            lines.append("}")

        lines.append("")

        return "\n".join(lines)

# -----------------------------------------------------
# Motor driver functions
# -----------------------------------------------------

    def generate_motor_functions(self, model):
        lines = []

        motors = self.find_objects(model, "Motor")
        drivers = self.find_objects(model, "MotorDriver")

        if not motors:
            return ""

        lines.append("// Motor control functions")

        for index, motor in enumerate(motors):
            attrs = self.get_attributes(motor)

            side = str(attrs.get("side", "")).lower()
            prefix = f"motor_{index}"

            # Compensate for opposite motor orientation.
            direction = (
                "HIGH" if side == "left" else "LOW"
            )

            lines.append(f"""
void {prefix}_set_speed(int speed) {{

    speed = constrain(speed, 0, 255);

    digitalWrite(
        MOTOR_{index}_DIRECTION_PIN,
        {direction}
    );

    analogWrite(
        MOTOR_{index}_PWM_PIN,
        speed
    );
}}
""")

        lines.append("void motor_driver_stop() {")

        for index, motor in enumerate(motors):
            lines.append(
                f"    analogWrite(MOTOR_{index}_PWM_PIN, 0);"
            )

        lines.append("}")

        if drivers:
            attrs = self.get_attributes(drivers[0])

            if attrs.get("standbyPin") is not None:
                lines.append("""
void motor_driver_enable() {
    digitalWrite(MOTOR_DRIVER_STANDBY_PIN, HIGH);
}

void motor_driver_disable() {
    digitalWrite(MOTOR_DRIVER_STANDBY_PIN, LOW);
}
""")

        return "\n".join(lines)

    # -----------------------------------------------------
    # LED functions
    # -----------------------------------------------------

    def generate_led_functions(self, model):
        leds = self.find_objects(model, "StatusLED")

        if not leds:
            return ""

        lines = ["// Status LED functions"]

        for index, led in enumerate(leds):
            attrs = self.get_attributes(led)

            count = max(1, int(attrs.get("ledCount", 1)))

            lines.append(f"""
CRGB status_led_pixels_{index}[{count}];

void status_led_{index}_init() {{

    FastLED.addLeds<WS2812B, STATUS_LED_{index}_PIN, GRB>(
        status_led_pixels_{index},
        STATUS_LED_{index}_LED_COUNT
    );

    FastLED.clear();
    FastLED.show();
}}

void status_led_{index}_off() {{

    FastLED.clear();
    FastLED.show();
}}

void status_led_{index}_set_colour(
    uint8_t red,
    uint8_t green,
    uint8_t blue
) {{

    for (int i = 0; i < STATUS_LED_{index}_LED_COUNT; i++) {{
        status_led_pixels_{index}[i] = CRGB(
            red,
            green,
            blue
        );
    }}

    FastLED.show();
}}
""")

        return "\n".join(lines)

# -----------------------------------------------------
# Setup function
# -----------------------------------------------------

    def generate_setup(self, model):
        lines = []
        lines.append("void setup() {")
        lines.append("    Serial.begin(9600);")
        lines.append("    Serial.println();")
        lines.append('    Serial.println("Robot initialized");')

        # Distance sensors
        for index, sensor in enumerate(
            self.find_objects(model, "DistanceSensor")
        ):
            lines.append(
                f"    pinMode(DISTANCE_SENSOR_{index}_TRIG_PIN, OUTPUT);"
            )

            lines.append(
                f"    pinMode(DISTANCE_SENSOR_{index}_ECHO_PIN, INPUT);"
            )

        # Motors
        motors = self.find_objects(model, "Motor")

        for index, motor in enumerate(motors):
            lines.append(
                f"    pinMode(MOTOR_{index}_PWM_PIN, OUTPUT);"
            )

            lines.append(
                f"    pinMode(MOTOR_{index}_DIRECTION_PIN, OUTPUT);"
            )

        # Motor driver
        drivers = self.find_objects(model, "MotorDriver")

        if drivers:
            attrs = self.get_attributes(drivers[0])

            if attrs.get("standbyPin") is not None:
                lines.append(
                    "    pinMode(MOTOR_DRIVER_STANDBY_PIN, OUTPUT);"
                )

                lines.append(
                    "    digitalWrite(MOTOR_DRIVER_STANDBY_PIN, HIGH);"
                )

        # LEDs
        for index, led in enumerate(
            self.find_objects(model, "StatusLED")
        ):
            lines.append(
                f"    status_led_{index}_init();"
            )

        # Line tracker channels
        for channel in self.find_objects(model, "LineChannel"):
            attrs = self.get_attributes(channel)

            pin = attrs.get("pin", 0)

            lines.append(
                f"    pinMode({pin}, INPUT);"
            )

        lines.append("}")
        lines.append("")

        return "\n".join(lines)

# -----------------------------------------------------
# Loop function
# -----------------------------------------------------

    def generate_loop(self, model):
        lines = ["void loop() {"]

        # Read distance sensors periodically.
        for index, sensor in enumerate(
            self.find_objects(model, "DistanceSensor")
        ):
            lines.append(f"""
    static unsigned long last_distance_{index} = 0;

    if (millis() - last_distance_{index} >=
        DISTANCE_SENSOR_{index}_READ_INTERVAL_MS) {{

        last_distance_{index} = millis();

        float distance = distance_sensor_{index}_read();

        Serial.print("Distance sensor {index}: ");
        Serial.print(distance);
        Serial.println(" cm");
    }}
""")

        # Read line tracker channels.
        channels = self.find_objects(model, "LineChannel")

        if channels:
            lines.append("    // Read line tracker channels")

            for index, channel in enumerate(channels):
                attrs = self.get_attributes(channel)

                position = safe_name(
                    attrs.get("position", f"channel_{index}")
                ).lower()

                lines.append(
                    f"    int line_{position} = "
                    f"line_tracker_read_{position}();"
                )

        lines.append("    delay(10);")
        lines.append("}")

        return "\n".join(lines)

# -----------------------------------------------------
# Generate complete Arduino sketch
# -----------------------------------------------------

    def generate_sketch(self, model):
        model_name = self.get_model_name(model)

        if not self.validate_model(model):
            print(
                f"Skipping invalid model: {model_name}"
            )
            return None

        sections = [
            self.generate_header(model_name),
            self.generate_constants(model),
            self.generate_distance_functions(model),
            self.generate_line_functions(model),
            self.generate_motor_functions(model),
            self.generate_led_functions(model),
            self.generate_setup(model),
            self.generate_loop(model)
        ]

        return "\n".join(
            section for section in sections if section
        )

# -----------------------------------------------------
# Generate all models
# -----------------------------------------------------

    def generate_all(self):
        self.output_directory.mkdir(
            parents=True,
            exist_ok=True
        )

        models = self.get_instance_models()

        if not models:
            raise ValueError(
                "No instance models were found in the JSON file."
            )

        for model in models:
            model_name = self.get_model_name(model)

            print(f"Generating: {model_name}")

            sketch = self.generate_sketch(model)

            if sketch is None:
                continue
        
            model_directory = self.output_directory / safe_name(model_name)
            model_directory.mkdir(
                parents=True,
                exist_ok=True
            )

            filename = safe_name(model_name) + ".ino"
            output_path = model_directory / filename

            with open(
                output_path,
                "w",
                encoding="utf-8"
            ) as file:
                file.write(sketch)

            self.generated_files.append(output_path)

            print(f"Created: {output_path}")

        print("\nGeneration complete.")
        print(
            f"Generated {len(self.generated_files)} Arduino sketches."
        )


# ---------------------------------------------------------
# Main program
# ---------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python generator.py "
            "<model.json> [output_directory]"
        )
        sys.exit(1)

    model_path = sys.argv[1]

    output_directory = (
        sys.argv[2]
        if len(sys.argv) > 2
        else "generated"
    )

    generator = RobotCodeGenerator(
        model_path,
        output_directory
    )

    try:
        generator.load_model()
        generator.generate_all()

    except Exception as error:
        print(f"Error: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()

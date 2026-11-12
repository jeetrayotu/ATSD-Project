# ATSD-Project
Requirements:
- Python 3 installed
- A valid `.json` file


## Running the Generator

1. Open a terminal in the project directory.
2. Run the following command:

   ```bash
   python generator.py NewMetaModel.iml.json generated
   ```

Replace `NewMetaModel.iml.json` with your model filename if necessary.

3. The generated Arduino sketches will appear in the `generated` folder, with a separate folder for each instance model.

Uploading to Arduino
- Open the desired `.ino` file in the Arduino IDE.
- Select the correct Arduino board and port.
- Install any required libraries (such as FastLED).
- Click **Upload** to upload the generated code to the robot.
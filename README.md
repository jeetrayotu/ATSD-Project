# ATSD-Project
Requirements:
- Python 3 installed
- A valid `.json` file


## Running the Generator

1. Open a terminal in the project directory.
2. Run the following command:

   ```bash
   python generator.py <model.json> [output_directory]
   ```

3. The generated Arduino sketches will appear in the `generated` folder by default, with a separate folder for each instance model.

Uploading to Arduino
- Open the desired `.ino` file in the Arduino IDE.
- Select the correct Arduino board and port.
- Install any required libraries (such as FastLED).
- Click **Upload** to upload the generated code to the robot.

## Backend Usage

### Run using uv

Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/#installation-methods) (Python ≥ 3.14 required).

```bash
git clone https://github.com/CORRUPT3D-Code/SQA_Project.git
cd SQA_Project
uv run sqa server start
```

Once the server is up, open http://localhost in your browser.

## Backend Development

### Setup

```bash
uv run poe setup
```

This runs `uv sync --all-groups` to install all dependencies including dev and lint extras.

### Building

#### Wheel

```bash
uv build
```

Produces a `.whl` file suitable for distribution via `uvx`.

#### Standalone executable

Requires one of the [C compilers supported by Nuitka](https://github.com/Nuitka/Nuitka?tab=readme-ov-file#c-compiler).

```bash
uv run poe build
```

### Testing

```bash
uv run pytest
```

Tests run in parallel across all available CPU cores via `pytest-xdist`.

### Formatting

```bash
uv run poe format          # format entire project
uv run poe format -- path  # format a specific path
```

### Clean

Remove all temporary and generated files:

```bash
uv run poe clean
```

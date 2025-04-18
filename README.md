# image2jack

## Description

A simple tool to turn images into [JACK](https://jackaudio.org/)-Audio streams and back.


## Features

- One channel for each corresponding RGB(A) value
- Autoconnect to another JACK client´s inputs/outputs based on regex filters

### TODO

- [ ] Single-channel out/input
- [ ] Choosable image channels
- [ ] Saving to file


## Installation

**Disclaimer:** I've only tested this under Linux, so be warned when trying to use it on other operating systems.

1. **Install Python**
  To use this, you will need [Python 3.13](https://www.python.org/) and preferrably [uv](https://docs.astral.sh/uv/) as a project manager, though installing dependencies through `venv` should also work.

2. **Install JACK**
  Follow the installation instructions for your platform:
  - Linux: Use your package manager (e.g., `sudo apt install jackd` on Ubuntu).
  - MacOS: Use [Homebrew](https://brew.sh/) (`brew install jack`).
  - Windows: Download and install JACK from the [official site](https://jackaudio.org/downloads/).

3. **Clone Repository**
  ```bash
  git clone https://github.com/minemo/image2jack.git
  cd image2jack
  ```

4. **Install Dependencies**
  ```bash
  pip -m venv venv
  # Linux and Mac
  source venv/bin/activate
  # Windows
  venv\Scripts\activate.bat

  pip install -r requirements.txt
  ```


## Usage

```bash
python main.py <image_input> <image_output> -a -s
```
Replace `<image_input>` and `<image_output>`_(Placeholder)_ with your respective images.
This will send each of your images channels as a seperate audio-stream and try to send them to [Cardinal](https://cardinal.kx.studio/) by default.
To change which program it will send the audio to, either remove the `-a` flag, or change the regex pattern via `--cinpat` and `--coutpat`.


## License

This project is licensed under the GNU GPLv3 License. See the [LICENSE](https://github.com/minemo/image2jack/tree/LICENSE) file for details.

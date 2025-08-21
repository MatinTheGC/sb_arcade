# SpongeBob Flash Game Arcade

This project is a preservation of classic SpongeBob SquarePants Flash games with a focus on maintaining the original archive setup and proxy server behavior. The project no longer includes automatic installation of required Python packages. Instead, please follow the manual installation instructions outlined below for your operating system.

## Installation Instructions

### Prerequisites

- **Transmission Daemon**: The script requires a Transmission daemon to be running. Follow the steps below to install and run Transmission on your operating system.
- **Python Packages**: You need to manually install the following Python packages:
  - `transmission-rpc`
  - `requests`
  - `beautifulsoup4`
  - `selenium`
  - `selenium-wire`
  - `tqdm`

### Windows

1. **Transmission Daemon**:
   - Download and install Transmission for Windows from its official website or a trusted source.
   - Configure and start the Transmission daemon.

2. **Python Environment**:
   - Open a PowerShell prompt.
   - Navigate to the project directory:

     ```pwsh
     cd c:\Users\Matin\Documents\flash\python
     ```

   - Create and activate a virtual environment (optional but recommended):

     ```pwsh
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```

   - Install the required packages:

     ```pwsh
     pip install transmission-rpc requests beautifulsoup4 selenium selenium-wire tqdm
     ```

### Linux

1. **Transmission Daemon**:
   - Install Transmission daemon using your package manager. For Debian/Ubuntu-based systems:

     ```bash
     sudo apt-get update && sudo apt-get install transmission-daemon
     ```

   - Start and enable the Transmission daemon:

     ```bash
     sudo systemctl start transmission-daemon
     sudo systemctl enable transmission-daemon
     ```

2. **Python Environment**:
   - Open a terminal and navigate to the project directory:

     ```bash
     cd ~/path/to/flash/python
     ```

   - (Optional) Create and activate a virtual environment:

     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

   - Install the required packages:

     ```bash
     pip install transmission-rpc requests beautifulsoup4 selenium selenium-wire tqdm
     ```

### macOS

1. **Transmission Daemon**:
   - Install Transmission via Homebrew:

     ```bash
     brew install transmission
     ```

   - Start the Transmission daemon. You might need to configure it to run as a background service depending on your setup.

2. **Python Environment**:
   - Open Terminal and navigate to the project directory:

     ```bash
     cd /path/to/flash/python
     ```

   - (Optional) Create and activate a virtual environment:

     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

   - Install the required packages:

     ```bash
     pip install transmission-rpc requests beautifulsoup4 selenium selenium-wire tqdm
     ```

## Usage

Run the arcade script manually once all prerequisites are met:

```bash
python arcade.py
```

## Notes

- This project no longer automatically installs Python packages. Ensure that all dependencies are manually installed prior to running the scripts.
- Refer to each script's header comments for additional configuration options and usage details.

---

*For further information or troubleshooting, please refer to the official documentation of each software component used in this project.*

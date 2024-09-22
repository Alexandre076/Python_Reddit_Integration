import os
import subprocess
import sys
from logger_setup import setup_logging, log_and_print

#Run this script if not using docker. This script creates the environment and then calls the main.py function.

# Set up logging
setup_logging()

log_and_print("Starting script execution...")
# Define the name of the virtual environment
env_name = 'env'
requirements_file = 'requirements.txt'
main_script = 'main.py'

# Function to check if the virtual environment already exists
def check_env_exists(env_name):
    return os.path.exists(env_name)

# Function to create a virtual environment
def create_virtual_env(env_name):
    print(f"Creating virtual environment: {env_name}...")
    subprocess.check_call([sys.executable, '-m', 'venv', env_name])
    print("Virtual environment created successfully.")

# Function to install dependencies from requirements.txt
def install_requirements(env_name):
    print("Installing dependencies from requirements.txt...")
    subprocess.check_call([os.path.join(env_name, 'Scripts', 'pip'), 'install', '-r', requirements_file])
    print("Dependencies installed successfully.")

# Function to run the main.py script
def run_main_script(env_name):
    print(f"Running {main_script}...")
    subprocess.check_call([os.path.join(env_name, 'Scripts', 'python'), main_script])

# Check if the virtual environment exists
log_and_print("Checking if virtual environment exists...")
if not check_env_exists(env_name):
    log_and_print("Virtual environment does not exist. Creating it now...")
    create_virtual_env(env_name)

# Install requirements
install_requirements(env_name)

# Run the main script
run_main_script(env_name)

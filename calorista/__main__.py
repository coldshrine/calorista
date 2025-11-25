import subprocess
import sys
from pathlib import Path

def main():
    # Your existing main script logic here
    from .main import main as main_func
    main_func()

def run_app():
    """Run the Streamlit app"""
    streamlit_app_path = Path(__file__).parent / "streamlit_app.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(streamlit_app_path)])

if __name__ == "__main__":
    main()
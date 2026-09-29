"""
Live Ingestion Loop for BharatRiskAI Nowcasting System

This script continuously monitors MOSDAC downloads and triggers inference
for new weather data. It integrates with the NowcastingInferenceEngine
to provide real-time hazard predictions.
"""

import os
import sys
import time
import logging
from typing import Dict, Any
import requests

# Add the root directory to sys.path to ensure imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from ml.nowcasting.inference import NowcastingInferenceEngine
"""
Live Ingestion Loop for BharatRiskAI Nowcasting System

This script continuously monitors MOSDAC downloads and triggers inference
for new weather data. It integrates with the NowcastingInferenceEngine
to provide real-time hazard predictions.
"""

import os
import time
import logging
from typing import Dict, Any
from datetime import datetime
import requests

from ml.nowcasting.inference import NowcastingInferenceEngine
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('live_ingestion.log'),
        logging.StreamHandler()
    ]
)

class MOSDACDownloader:
    """Handles downloading and processing of MOSDAC data."""

    def __init__(self, base_url: str = "https://mosdac.gov.in/data/", download_dir: str = "data/mosdac"):
        self.base_url = base_url
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
        self.last_processed = self._get_last_processed()

    def _get_last_processed(self) -> str:
        """Get the timestamp of the last processed file."""
        try:
            with open(os.path.join(self.download_dir, "last_processed.txt"), "r") as f:
                return f.read().strip()
        except (FileNotFoundError, IOError):
            return ""

    def _update_last_processed(self, timestamp: str) -> None:
        """Update the timestamp of the last processed file."""
        with open(os.path.join(self.download_dir, "last_processed.txt"), "w") as f:
            f.write(timestamp)

    def _download_file(self, url: str, filename: str) -> bool:
        """Download a file from the given URL."""
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            filepath = os.path.join(self.download_dir, filename)
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logging.info(f"Downloaded {filename} successfully.")
            return True
        except Exception as e:
            logging.error(f"Failed to download {filename}: {e}")
            return False

    def poll_for_new_data(self) -> Dict[str, Any]:
        """Poll MOSDAC for new data files."""
        # Example: Poll a specific endpoint or directory
        # This is a placeholder for the actual MOSDAC API or directory listing logic
        # For now, we'll simulate a new file being available
        new_files = []
        
        # Simulate checking for new files
        for root, _, files in os.walk(self.download_dir):
            for file in files:
                filepath = os.path.join(root, file)
                if os.path.getmtime(filepath) > self.last_processed:
                    new_files.append(filepath)
        
        if new_files:
            logging.info(f"Found new files: {new_files}")
            return new_files[0]  # Return the most recent file
        return None

class NowcastingIngestionLoop:
    """Main ingestion loop for processing MOSDAC data."""

    def __init__(self, inference_engine: NowcastingInferenceEngine):
        self.inference_engine = inference_engine
        self.downloader = MOSDACDownloader()

    def process_file(self, filepath: str) -> None:
        """Process a single file and trigger inference."""
        try:
            # Simulate reading and parsing the file
            # In a real scenario, this would involve parsing the MOSDAC data format
            data = self._parse_mosdac_file(filepath)
            
            # Trigger inference
            result = self.inference_engine.predict_nowcast(data)
            
            # Log the result
            logging.info(f"Inference result: {result}")
            
            # Update last processed timestamp
            self.downloader._update_last_processed(datetime.now().isoformat())
        except Exception as e:
            logging.error(f"Error processing file {filepath}: {e}")

    def _parse_mosdac_file(self, filepath: str) -> Dict[str, Any]:
        """Parse MOSDAC data file into a dictionary."""
        # Placeholder for actual parsing logic
        # This is a mock implementation for demonstration
        mock_data = {
            "rainfall_15m_rate": 45.0,
            "radar_reflectivity_dbz": 48.0,
            "cape_j_kg": 2100.0,
            "lifted_index": -4.0,
            "elevation": 4.5,
            "drainage_score": 35.0,
            "iwv": 45.0,
            "iwv_change": 5.0,
            "ctt": -45.0,
            "ctt_drop_rate": 2.5,
            "qpe_mm_hr": 10.0,
            "cin_j_kg": -80.0,
            "low_level_convergence": 0.12,
            "wind_shear_ms": 12.0,
            "slope_degrees": 3.0,
        }
        return mock_data

    def run(self, interval: int = 300) -> None:
        """Run the ingestion loop."""
        logging.info("Starting live ingestion loop...")
        while True:
            new_file = self.downloader.poll_for_new_data()
            if new_file:
                self.process_file(new_file)
            time.sleep(interval)


if __name__ == "__main__":
    import sys
    import os
    
    # Ensure the script is run from the root directory
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
    
    # Initialize inference engine
    from ml.nowcasting.inference import NowcastingInferenceEngine
    inference_engine = NowcastingInferenceEngine(device="cpu")
    
    # Start ingestion loop
    ingestion_loop = NowcastingIngestionLoop(inference_engine)
    ingestion_loop.run()
import subprocess
import os
import logging

# Configure logging to write logs to a file
logging.basicConfig(
    filename='execute.log',  # Log file name
    level=logging.INFO,  # Log level
    format='%(asctime)s - %(levelname)s - %(message)s',  # Log message format
)

def execute_files():
    """
    Executes a list of Python files in sequence using subprocess.
    """
    # Ensure paths are relative to the script directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    files = [
        os.path.join(base_dir, 'main_pipeline.py'),
        # os.path.join(base_dir, 'scraper', 'scraper.py'),
        # os.path.join(base_dir, 'scraper', 'create_knowledge_base_from_json.py'),
        # os.path.join(base_dir, 'knowledge_base', 'generate_embeddings.py'),
        # os.path.join(base_dir, 'knowledge_base', 'merge_embeddings.py')
    ]
    
    for file in files:
        try:
            logging.info(f"Starting execution of {file}...")
            subprocess.run(['python', file], check=True, shell=True)  # Use 'python' and shell=True for Windows
            logging.info(f"Successfully executed {file}.")
        except subprocess.CalledProcessError as e:
            logging.error(f"Error executing {file}: {e}")
            break
        except Exception as e:
            logging.error(f"Unexpected error while executing {file}: {e}")
            break

if __name__ == "__main__":
    logging.info("Execution of files started.")
    execute_files()
    logging.info("Execution of files completed.")

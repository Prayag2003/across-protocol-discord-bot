import subprocess
import sys
import os
from datetime import datetime
from loguru import logger
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pipeline.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

class PipelineExecutor:
    def __init__(self, script_path="privilieged_commands/update_pipeline.sh"):
        self.script_path = script_path
        
    def make_script_executable(self):
        """Make the bash script executable"""
        try:
            os.chmod(self.script_path, 0o755)
            logging.info("Made script executable")
        except Exception as e:
            logging.error(f"Failed to make script executable: {str(e)}")
            raise

    def run_pipeline(self):
        """Execute the pipeline script and handle any errors"""
        start_time = datetime.now()
        logging.info(f"Starting pipeline execution at {start_time}")
        
        try:
            self.make_script_executable()
            
            process = subprocess.Popen(
                [f"./{self.script_path}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,  
                text=True,
                shell=True
            )

            logger.info("Process", process)
            
            stdout_lines = []
            stderr_lines = []

            while True:
                stdout_output = process.stdout.readline()
                stderr_output = process.stderr.readline()

                if stdout_output == '' and stderr_output == '' and process.poll() is not None:
                    break

                if stdout_output:
                    logging.info(stdout_output.strip())
                    stdout_lines.append(stdout_output.strip())
                if stderr_output:
                    logging.error(stderr_output.strip())
                    stderr_lines.append(stderr_output.strip())
            
            return_code = process.poll()
            
            if return_code != 0:
                full_stderr = '\n'.join(stderr_lines)
                full_stdout = '\n'.join(stdout_lines)
                raise subprocess.CalledProcessError(return_code, self.script_path, full_stderr)

            end_time = datetime.now()
            duration = end_time - start_time
            logging.info(f"Pipeline completed successfully in {duration}")
            return True

        except subprocess.CalledProcessError as e:
            # Log the captured stderr output along with the error message
            logging.error(f"Pipeline failed with error: {str(e)}")
            logging.error(f"Error output: {e.stderr}")  # Now should contain full stderr
            raise

        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            raise

    
if __name__ == "__main__":
    try:
        executor = PipelineExecutor()
        executor.run_pipeline()
    except Exception as e:
        logging.error(f"Failed to execute pipeline: {str(e)}")
        sys.exit(1)
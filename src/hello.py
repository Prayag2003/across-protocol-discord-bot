import os
from datetime import datetime

def write_to_files():
    """
    Generates two files (a.txt and b.txt) and writes the current date and time into them.
    """
    # Get the current date and time
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Define file paths
    file_a = "a50.txt"
    file_b = "b50.txt"
    
    try:
        # Write current time to a.txt
        with open(file_a, "w") as file:
            file.write(f"Current date and time: {current_time}\n")
        print(f"{file_a} created successfully.")
        
        # Write current time to b.txt
        with open(file_b, "w") as file:
            file.write(f"Current date and time: {current_time}\n")
        print(f"{file_b} created successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    write_to_files()

import os
import requests
import pandas as pd


class ETLTools:
    """
    A utility class for ETL (Extract, Transform, Load) operations.
    """
    def __init__(self):
        pass
    
    def extract_load(self, url: str, output_folder: str, output_format: str)->str:
        """
        Extracts load from a given URL and saves it to the specified output path in the desired format.

        Args:
            url (str): The URL to extract data from.
            output_folder (str): The folder where the extracted data will be saved.
            output_format (str): The format in which to save the data ('csv' or 'json').
            
        Returns:
            str: A message indicating the success or failure of the extraction process.
        """
        try:
            output_format = output_format.lower()
            if output_format not in {"csv", "json"}:
                return f"Unsupported output format: {output_format}"
            os.makedirs(output_folder, exist_ok=True)
            response = requests.get(url)
            response.raise_for_status()  # Raise an error for bad responses
            data = response.json()  # Assuming the data is in JSON format
            
            filename = os.path.basename(url)
            output_path = os.path.join(output_folder, f"{filename}.{output_format.lower()}")

            df = pd.DataFrame(data)
            if output_format == 'csv':
                df.to_csv(output_path, index=False)
            elif output_format == 'json':
                df.to_json(output_path, orient='records', lines=True)
            
            return f"Data extracted and saved to {output_path} in {output_format.upper()} format."

        except requests.exceptions.RequestException as e:
            return f"Error during data extraction: {e}"
        except Exception as e:
            return f"An error occurred: {e}"
        
        
    def transform_load_context(self, file_path: str, k: int = 3) -> str:
        """
        Main motive of  this function to get the top k(default 3) rows of the data from the given file path.
        as it help to build the context for the next step of the ETL process. It reads the data from the specified file path
        Args:
            file_path (str): The path to the file containing the data to be transformed.
            
        Returns:
            str: A message indicating the success or failure of the transformation process.
        """
        
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension == '.csv':
            df = pd.read_csv(file_path)
        elif file_extension == '.json':
            df = pd.read_json(file_path, lines=True)
        else:
            return f"Unsupported file format: {file_extension}"
        
        
        return str(df.head(k))
        
    def execute_code(self, code: str) -> str:
        """
        Executes the provided Python code and returns the output or any errors encountered during execution.
        
        Args:
            code (str): The Python code to be executed.
            
        Returns:
            str: The output of the executed code or an error message if an exception occurs.
        """
        try:
            exec(code)
            return "Code executed successfully."
        except Exception as e:
            return f"Error executing code: {e}"
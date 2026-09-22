import requests
import os
from pathlib import Path
import json
import glob
import time
import logging
import threading
from datetime import datetime
import re
import sys

try:
    from tqdm.auto import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print("\n[INFO] 'tqdm' Library is Not Installed on your system. Hence, the Progress Bar while Downloading Files will appear a bit differently.\n")

token_url = "https://mosdac.gov.in/download_api/gettoken"
search_url = "https://mosdac.gov.in/apios/datasets.json"
check_internet_url = "https://mosdac.gov.in/download_api/check-internet"
download_url = "https://mosdac.gov.in/download_api/download"
refresh_url = "https://mosdac.gov.in/download_api/refresh-token"
logout_url = "https://mosdac.gov.in/download_api/logout"

def preprocess_json(raw_json):
    """
    Escapes Unescaped Backslashes for Windows-style Paths provided in 'config.json' 
    """
    fixed_json = re.sub(r'(?<!\\)\\(?![\\/"bfnrtu])', r'\\\\', raw_json)
    fixed_json = re.sub(r'(?<!\\)\\(?=\s*")', r'\\\\', fixed_json)

    return fixed_json

def load_config(): 
    """Loads and validates configuration from config.json."""
    try:
        with open("config.json", "r") as file:
            raw_config = file.read()
        
        try:
            config = json.loads(raw_config)
        except json.JSONDecodeError:
            # Preprocess the JSON to fix common Windows Path issues
            fixed_json = preprocess_json(raw_config)
            try:
                config = json.loads(fixed_json)
            except json.JSONDecodeError:
                print("[ERROR] Invalid JSON format in 'config.json'! Please correct it and Try Again.")
                sys.exit(1)

        # Validate required fields
        required_fields = ["user_credentials", "search_parameters"]
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing Required Config Section: {field} inside 'config.json'")
            
        # Sets Current Directory for Download if 'download_settings' not specified
        if "download_settings" not in config:
            print("\n[Warning]: 'download_settings' not set in 'config.json'. Downloading in the Current Directory..")
            config["download_settings"] = {
                "download_path": ""
            }
        return config
    
    except FileNotFoundError as e:
        print("[ERROR] 'config.json' Not Found!")
        exit(1)
        
    except ValueError as e:
        print(f"[ERROR] in 'config.json': {e}")
        exit(1)

config_file = load_config()

# Fetching Information from 'config.json'
user_creds = config_file['user_credentials']
username = user_creds.get("username/email", "")
password = user_creds.get("password", "")

download_settings = config_file['download_settings']

# Retrives Download Path from 'config.json'
download_path = download_settings.get("download_path").replace("\\", "/") or os.path.join(os.getcwd(), "MOSDAC Data Download")

use_date_structure = download_settings.get("organize_by_date", False)
skip_user_input = download_settings.get("skip_user_input", False)
generate_logs = download_settings.get("generate_error_logs", False)

bool_fields = {
    "organize_by_date": use_date_structure,
    "skip_user_input": skip_user_input,
    "generate_error_logs": generate_logs
}

invalid_fields = []

# Validates Fields of 'download_settings' of 'config.json'
for field, value in bool_fields.items():
    if not isinstance(value, bool):
        invalid_fields.append((field, value))
    
if invalid_fields:
    print("\n[ERROR] Configuration Error: The following fields must be either: true or false (Boolean):")
    for field, value in invalid_fields:
        print(f" - '{field}' has Invalid Value: {value}")
    print("\nPlease Correct these in your 'config.json' and Try Again.\n")
    sys.exit(1)

search_params = config_file['search_parameters']
datasetId = search_params.get("datasetId", "")
startTime = search_params.get("startTime", "")
endTime = search_params.get("endTime", "")
startIndex = int(search_params.get("startIndex", 1) or 1)
count = search_params.get("count", "")
boundingBox = search_params.get("boundingBox", "")
gId = search_params.get("gId", "")



logger = logging.getLogger("client_error_logger")

try:
    if generate_logs:
        # Set up Error Logging if enabled
        error_logs_dir = download_settings.get("error_logs_dir") or os.path.join(os.getcwd(), "error_logs")
        os.makedirs(error_logs_dir, exist_ok=True)

        date_str = datetime.now().strftime("%d-%m-%Y")
        log_file_path = os.path.join(error_logs_dir, f"{date_str}_error.log")

        file_handler = logging.FileHandler(log_file_path)
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%d-%m-%Y %H:%M:%S"
        )

        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.setLevel(logging.ERROR)
        logger.propogate = False
except PermissionError:
        print(f"\n[ERROR]: No Permission to Write on '{error_logs_dir}'. Please Check and Update Directory Permissions or use Another Directory for Storing Logs.\n")
        sys.exit(1)
except Exception as e:
        print(f"\nException encountered in Generating Logs: {e}\n")

def supports_color():
    if sys.platform != "win32":
        return True
    return "ANSICON" in os.environ or "WT_SESSION" in os.environ or os.environ.get("TERM_PROGRAM") == "vscode"

if supports_color():
    GREEN = "\033[92m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"
else:
    GREEN = RED = RESET = BOLD = UNDERLINE = ""

def get_token():
    """Fetch access token from the token endpoint."""

    data = {
        "username": username, 
        "password": password
    }
    try:
        response = requests.post(token_url,json=data)

        # Catches and Displays - 'Server Maintainance' messages from Server Side
        if response.status_code == 503:
            print("Service Unavailable: ", response.json().get("message"))
            
        # Checks for Validation Errors before Raising Exceptions for Other Errors
        if response.status_code == 400:
            try:
                resp = response.json()
                err_msg = resp['error']
                print(f"\n[ERROR] Validation Error: {err_msg}.\n")
                if generate_logs:
                    logger.error(f"Validation Error was encountered while Fetching Token.\nHere are the Error Details: {err_msg}")
            except ValueError:
                print("\n[ERROR] Received status 400 but could not parse response.\n")
                if generate_logs:
                    logger.error("Validation Error: Status 400 [Validation Error] received but response was not JSON.", exc_info=True)
            sys.exit(1)

        if response.status_code == 401:
            try:
                resp = response.json()
                err_msg = resp['error']
                print(f"{err_msg}\n")
                if generate_logs:
                    logger.error(f"{err_msg}\n")
            except ValueError:
                print("\n[ERROR] Received status 401 but could not parse response.\n")
                if generate_logs:
                    logger.error("Validation Error: Status 401 [Invalid Username/Password] received but response was not JSON.", exc_info=True)
            sys.exit(1)    

        response.raise_for_status()
        token_response = response.json()
        return {
            "access_token": token_response.get("access_token"),
            "refresh_token": token_response.get("refresh_token")
        }, username
    
    except requests.exceptions.RequestException as e:
        
        error_msg = str(e)
        if '503 Server Error' in error_msg:
            print("\nServer Unavailable: The server is currently unreachable or not responding.\nPlease Try Again later or Contact Support if the issue persists. Thank you for your patience!\n")
            if generate_logs:
                logger.error("\nServer Unavailable: The server is currently unreachable or not responding.\nPlease Try Again later or Contact Support if the issue persists. Thank you for your patience!\n")
            sys.exit(1)
        elif 'Service Unavailable for url' in error_msg:
            print("\nServer Unavailable: The server is currently unreachable or not responding.\nPlease Try Again later or Contact Support if the issue persists. Thank you for your patience!\n")
            if generate_logs:
                logger.error("\nServer Unavailable: The server is currently unreachable or not responding.\nPlease Try Again later or Contact Support if the issue persists. Thank you for your patience!\n")
            sys.exit(1)
        elif 'Not Found for url' in error_msg:
            print("\nServer Unavailable: The server is currently unreachable or not responding.\nPlease Try Again later or Contact Support if the issue persists. Thank you for your patience!\n")
            if generate_logs:
                logger.error("\nServer Unavailable: The server is currently unreachable or not responding.\nPlease Try Again later or Contact Support if the issue persists. Thank you for your patience!\n")
            sys.exit(1)
        elif 'Max retries exceeded with url: /download_api/gettoken':
            print("\nServer Unavailable: The server is currently unreachable or not responding.\nPlease Try Again later or Contact Support if the issue persists. Thank you for your patience!\n")
            if generate_logs:
                logger.error("\nServer Unavailable: The server is currently unreachable or not responding.\nPlease Try Again later or Contact Support if the issue persists. Thank you for your patience!\n")
            sys.exit(1)
        else:
            print("[ERROR] Error Occured in 'get_token()': ", error_msg)
            if generate_logs:
                logger.error("Error fetching Access Token: ", exc_info=True) 

        sys.exit(1) 

def format_size(size_mb):
    if size_mb < 1024:
        return f"{size_mb:,.2f} MB"
    elif size_mb < 1024 ** 2:
        size_gb = size_mb / 1024
        return f"{size_gb:,.2f} GB"
    else:
        size_tb = size_mb / (1024 ** 2)
        return f"{size_tb:,.2f} TB"

# Fetches Total Results found for User's Search
def search_results():
    """Fetches all data from the search endpoint using pagination.""" 
    print()
    print("Searching Data for Provided Parameters...")
    data = {"datasetId": datasetId}

    optional_parameters = {
    "startTime": startTime,
    "endTime": endTime,
    "count": count,
    "boundingBox": boundingBox,
    "gId": gId
    }

    # Filters out Empty Values
    data.update({k: v for k, v in optional_parameters.items() if v})

    try:
        res = requests.get(search_url, params=data)
        if res.status_code == 200:
            list = res.json()
            totalResults = list["totalResults"]
            totalSize = list["totalSizeMB"]
            itemsPerPage = list["itemsPerPage"]

            formatted_size = format_size(totalSize)

            if count != "":
                if skip_user_input:
                    print(f"\n{UNDERLINE}{itemsPerPage}{RESET} Files Found for {datasetId}{RESET}")
                else:
                    print(f"\n{UNDERLINE}{itemsPerPage}{RESET} Files Found for {datasetId}{RESET}.\nDo you want to Download them? [Y/N]: ")
                return list['itemsPerPage']

            if skip_user_input:
                print(f"\n{UNDERLINE}{totalResults:,}{RESET} Files Found with Total Size of {UNDERLINE}{formatted_size}{RESET}")
            else:
                print(f"\n{UNDERLINE}{totalResults:,}{RESET} Files Found with Total Size of {UNDERLINE}{formatted_size}{RESET}.\nDo you want to Download them? [Y/N]: ")
            return list["totalResults"]
        
        elif res.status_code // 100 in [4, 5]: 
            list = res.json()
            error_message = list['message'][0] 
            print(f"\n[ERROR] Error Fetching Data from Search Endpoint. Please enter correct 'search_parameters' in your 'config.json' and try again.\n\nStatus Code: {res.status_code}\nError Message: {error_message}\n")
            if generate_logs:
                logger.error(f"\n\nError Fetching Data from Search Endpoint.\n\nError Message: {error_message}\nError Details: {list}\n")
            sys.exit(1)
        
    except (requests.ConnectionError, requests.Timeout):
        print("\n[ERROR] Network Error: No Internet Connection Detected.\nPlease check your Network Connection and try running the application again.\n")
        if generate_logs:
                logger.error("\nNetwork Error: No Internet Connection Detected.\nPlease check your Network Connection and try running the application again.\n", exc_info=True)
        sys.exit(1)

    except requests.exceptions.RequestException as e:
            print(f"\n[ERROR] Unexpected Status Code encountered in Search API's Response:\nError Details: {e}")
            if generate_logs:
                logger.error(f"\nUnexpected Status Code encountered in Search API's Response:\nError Details: ", exc_info=True)
            sys.exit(1)

def fetch_and_download_data(total_files, access_token, refresh_token):
    """Fetches all data from the search endpoint using pagination.""" 

    batch_size = 100
    start_Index = 1
    
    counter = 1
    download_count = 0
    skip_count = 0

    if skip_user_input == False:
        print("\nStarting with Data Download..")

    data = {"datasetId": datasetId}

    try:
        res = requests.get(check_internet_url, json=data)
        if res.status_code == 200:
            list = res.json()
            if list[0][0] == 1:
                print("This Product is not yet Released on Internet. Please try searching for a different 'datasetId'.\nExiting...")
                logout()
                sys.exit(1) # Exit if Product not Released on Internet

    except Exception as e:
        print("Exception occured while retrieving Internet Check: ", e)
        logger.error("Exception occured while retrieving Internet Check: ", exc_info=True)

    optional_parameters = {
    "startTime": startTime,
    "endTime": endTime,
    "count": count,
    "boundingBox": boundingBox,
    "gId": gId
    }
    # Filters out Empty Values
    data.update({k: v for k, v in optional_parameters.items() if v})

    try:
        while counter <= total_files: 
            
            data["startIndex"] = start_Index # Sets 'startIndex' for Pagination 
            try:
                res = requests.get(search_url, params=data)
                
                if res.status_code == 200:
                    list=res.json()
                    
                    if not list: # Stops if No More Results
                        break

                    for item in list['entries']:
                        identifier = item['identifier']
                        record_id = item['id']
                        prod_date = item['updated']
                        file_path = download_data(access_token, record_id, identifier, prod_date, counter, total_files)
                        
                        if file_path == 'NOT_RELEASED':
                            print("This Product is not yet Released on MOSDAC. Please try searching for a different 'datasetId'.\nExiting...")
                            logout()
                            sys.exit(1)

                        if file_path == "Invalid/Expired Token":
                            new_access_token = refresh_access_token(refresh_token)
                            if (new_access_token):
                                access_token = new_access_token['access_token'] # Updates New Access Token Globally
                                refresh_token = new_access_token['refresh_token'] # Updates New Refresh Token Globally
                                file_path = download_data(access_token, record_id, identifier, prod_date, counter, total_files)
                                counter += 1
                            else:
                                print("\n[ERROR] Token could not be Refreshed due to Invalid Refresh Token. Stopping Download...") 
                                if generate_logs:
                                    logger.error("\nThere was an Error encountered to Refresh Access Token due to Invalid Refresh Token provided, and hence, Download cannot proceed.")
                                logout()
                                sys.exit(1) # Exit if Token Refresh Fails

                        counter += 1

                        # Calculating Total Download Statistics
                        if file_path and os.path.exists(file_path):
                            download_count += 1
                        elif not file_path:
                            skip_count += 1

                    # Increments startIndex for Next Batch
                    start_Index += batch_size
                
                else:
                    print(f"\nUnexpected Status Code: {res.status_code}")
                    res.raise_for_status()

            except requests.exceptions.RequestException as e:
                res_json = res.json()
                error_message = res_json['message'][0] 
                print(f"\n\n[ERROR] Error Fetching Data from 'fetch_and_download_data()' method.\n\nError Message: {error_message}\nError Details: {e}")
                if generate_logs:
                    logger.error("\n\nError Fetching Data from 'fetch_and_download_data()' method.\n\nError Message: {error_message}\nError Details: ", exc_info=True)
                break # Exits loop on Error

        if counter == (total_files + 1):
            return True, download_count, skip_count
        else:
            return False, 0, 0
    except KeyboardInterrupt:
        print("\nDownload Interrupted By User. Exiting..")
        return False, 0, 0
    except PermissionError:
        print(f"\n[ERROR]: No Permission to Write on '{download_path}'. Please Check and Update Directory Permissions or use Another Directory.")
        if generate_logs:
            logger.error(f"\nPermission Error encountered: No Permission to Write to {download_path}, hence could not Proceed with Download.\nPlease Check and Update the Permission for Writing files inside: {download_path}")
        print("Logging Out..")
        logout()
        sys.exit(1)
    except Exception as e:
        print(f"\nException encountered in 'fetch_and_download_data()': {e}\n")

def get_user_input():
    try:
        if skip_user_input:
            print(f"\n{GREEN}'skip_user_input' Option Enabled in 'config.json'. Proceeding with Download...{RESET}")
            return "yes"
        
        while True:
            user_response = input().strip().lower()
            if user_response in ("y", "n", 'yes', 'no'):
                return user_response
            print(f"{RED}Invalid Input. Please Input 'Y' or 'N':{RESET}")
    except KeyboardInterrupt:
        print("\nDownload Cancelled By User. Exiting..\n")
        sys.exit(1)
    except Exception as e:
        print("[ERROR] Exception occured in 'get_user_input()': ", e)
        if generate_logs:
            logger.error("There was an Exception encounterd in the 'get_user_input()' method.\nError Details: ", exc_info=True)
        sys.exit(1)

def download_data(bearer_token, record_id, identifier, prod_date, counter, total_files): 
    """Download data using the record ID and collection."""
    # Creates Download Path if Not Already Exist
    os.makedirs(download_path, exist_ok=True)

    headers = {"Authorization": f"Bearer {bearer_token}"}
    params = {"id": record_id}

    tmp_file_path = '' 

    while True:

        RETRY_DELAYS = [10, 20, 30, 60, 90, 120]

        for attempt, delay in enumerate(RETRY_DELAYS + [None]):
            try:
                if use_date_structure: # Can be Put under fetch_and_download_data() for Single Time Use..
                    # Creates Dataset Specific Path in Download Directory
                    dataset_download_path = os.path.join(download_path, datasetId)
                    if prod_date == None:
                        print(f"\n[WARNING] File: '{identifier}' does not support 'organize_by_date' and hence, will be Downloaded inside the DatasetID directory instead..")
                        folder_structure = dataset_download_path
                    
                    else:
                        date_obj = datetime.strptime(prod_date, "%Y-%m-%dT%H:%M:%SZ")

                        year = date_obj.strftime("%Y")
                        day = date_obj.strftime("%d")
                        month_abbr = date_obj.strftime("%b").upper()

                        # Creates 'Archival' Date-Month Strcuture (eg: "09AUG")
                        day_month = f"{day}{month_abbr}"

                        # Creates Folder Strucutre (eg: 2025/09AUG)
                        folder_structure = os.path.join(dataset_download_path, year, day_month)
                else:
                    folder_structure = download_path

                os.makedirs(folder_structure, exist_ok=True) 

                file_path = os.path.join(folder_structure, identifier)

                # Checks if File Already Exists
                if os.path.exists(file_path):
                    print(f"\n[INFO] {identifier} Already Exists in {folder_structure}. Skipping Download..")
                    return None

                response = requests.get(download_url, headers=headers, params=params, stream=True, timeout=5)

                if response.status_code == 400:
                    resp = response.json()
                    err_msg = resp['error']
                    print(f"\n[ERROR] Validation Error: {err_msg}\n")
                    if generate_logs:
                        logger.error(f"\nValidation Error encountered in 'download_data' method.\nError Details: {err_msg}")
                    return None
                
                if response.status_code == 401:
                    error_data = response.json()
                    if error_data.get("code") == "NO_ACCESS_TOKEN":
                        return "Access Token Not Found. Please Login and Try Again."
                    elif error_data.get("code") == "INVALID_TOKEN":
                        return "Invalid/Expired Token"
                    
                if response.status_code == 404:
                    error_data = response.json()
                    if error_data.get("code") == "NOT_RELEASED":
                        return error_data.get("code")
                
                # If Rate Limit Reached, Error Handling According to the Err. Type
                if response.status_code == 429:
                    resp = response.json()
                    err_msg = resp['message']
                    err_type = resp['type']

                    if err_type == 'minute_limit':
                        print(f"\n{err_msg}")
                        time.sleep(20)
                        continue
                    elif err_type == 'daily_limit':
                        print(f"\n{err_msg}")
                        logout()
                        sys.exit(1) 
                            
                response.raise_for_status()
                
                # Get File Size 
                total_size = int(response.headers.get('Content-Length', 0))
                content_disposition = response.headers.get('Content-Disposition')

                # Extracts Filename 
                if content_disposition and 'filename=' in content_disposition: 
                    filename = identifier
                    # filename = os.path.splitext(filename)[0]
                else:
                    print(f"\n[WARNING] {identifier}: File Not Available on the Server. Skipping File..") 
                    if generate_logs:
                        logger.warning(f"\n[WARNING] {identifier}: This file is Not Available on the Server, and hence was Skipped during the Download.")
                    return None

                # os.makedirs(folder_structure, exist_ok=True)

                file_path = os.path.join(folder_structure, filename)
                tmp_file_path = file_path + ".part" # Temporary File

                # Checks if File Already Exists
                # if os.path.exists(file_path):
                #     print(f"\n[INFO] {filename} Already Exists in {folder_structure}. Skipping Download..")
                #     return None
                
                # If a previous Incomplete Download Exist, Delete it First
                if os.path.exists(tmp_file_path):
                    print(f"\n[INFO] Incomplete Download Found. Deleting and Restarting: {filename}")
                    os.remove(tmp_file_path)
                
                file_size = f"{total_size / (1024 * 1024):.2f} MB"

                # Displays File Size
                print(f"\n[{counter}/{total_files}] | Downloading: {filename} | File Size: {file_size}")
                
                with open(tmp_file_path, "wb") as file:
                    if HAS_TQDM:
                        try:
                            tqdm_kwargs = {}

                            if sys.platform == "win32":
                                tqdm_kwargs = {"ascii": True}
                            
                            start_time = time.time()
                            
                            with tqdm(
                                desc="Progress", total=total_size, unit='B', unit_scale=True, unit_divisor=1024, smoothing=0.3, miniters=1, mininterval=0.1, dynamic_ncols=True, **tqdm_kwargs
                            ) as bar:
                                bar.start_t = start_time

                                for chunk in response.iter_content(chunk_size=1048576): 
                                    if chunk:
                                        file.write(chunk)
                                        bar.update(len(chunk))
                                        bar.refresh()
                                
                                bar.close()

                        except PermissionError:
                            print(f"\n[ERROR]: No Permission to Write to {download_path}. Please Check File Permissions.")
                            print("Stopping Further Downloads..\n")
                            return "Permission Denied"          
                        except Exception as e:
                            print("[ERROR] Error Encountered in download_data():", e)
                            if generate_logs:
                                logger.error("An error was encountered while Downloading ")

                    else:                     
                        # Alternative for Download Progress - w/o TQDM
                        try:
                            download_size = 0
                            chunk_size = 1048576 
                            bar_length = 82

                            for chunk in response.iter_content(chunk_size=chunk_size):
                                if chunk:
                                    file.write(chunk)
                                    download_size += len(chunk)

                                    # Prints Progress in Percentage
                                    percent_done = (download_size / total_size)
                                    num_bars = int(bar_length * percent_done)
                                    bar_str=f"[{'#' * num_bars}{'.' * (bar_length - num_bars)}] {percent_done * 100:.1f}%"

                                    sys.stdout.write(f"\r{bar_str}")
                                    sys.stdout.flush()
                            print()
                        except PermissionError:
                            print(f"\n[ERROR]: No Permission to Write to {download_path}. Please Check and Update Directory Permissions.")
                            if generate_logs:
                                logger.error(f"\nPermission Error encountered: No Permission to Write to {download_path}, hence could not Proceed with Download.\nPlease Check and Update the Permission for Writing files inside: {download_path}")
                            print("Stopping Further Downloads..\n")
                            return "Permission Denied"

                # Renames Temp File to Final File after Successful Download
                os.rename(tmp_file_path, file_path)
                
                return file_path

            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                print(f"\n[WARNING] Network Error encountered: Please check your Internet connection and reconnect if needed.\nError Details: {e}")
                if delay is None:
                    print(f"\n[ERROR] Download Stopped after Multiple Attempts due to Network Error. Please check your Internet connection and Try Again.")
                    if generate_logs:
                        logger.error(f"\nDownload was Stopped after Multiple Attempts due to the encountered Network Error. Please check your Internet connection and Try Again.\n")
                    return None
                print(f"\n[INFO] Retrying in {delay} seconds...")
                if tmp_file_path and os.path.exists(tmp_file_path):
                    os.remove(tmp_file_path)
                time.sleep(delay)

            except requests.exceptions.RequestException as e:
                error_message = str(e)
                
                if "NOT FOUND for url" in error_message:
                    print(f"\n[WARNING] {identifier}: File Not Available on the Server. Skipping File..")
                    if generate_logs:
                        logger.warning(f"\n[WARNING] {identifier}: This file is Not Available on the Server, and hence was Skipped during the Download.")
                    return None
                elif os.path.exists(tmp_file_path):
                    print(f"\n[WARNING] Download was Interrupted due to Connection Loss. Resuming from the last point..")
                else:
                    print(f"\n[ERROR] Error downloading data.", e)
                    if generate_logs:
                        logger.error("[ERROR] Error encountered in 'download()' method.\nError Details: ", exc_info=True)
                    return None


def refresh_access_token(refresh_token):
    data = {"refresh_token": refresh_token}

    try:
        response = requests.post(refresh_url, json=data)

        if response.status_code == 400:
            resp = response.json()
            err_msg = resp['error']
            print(f"\n[ERROR] Validation Error: {err_msg}\n")
            if generate_logs:
                logger.error(f"There was an Error encountered regarding the Validation of Refresh Token.\nError Details: {err_msg}\nSolution: Please make sure the Refresh Token is not Tampered or modified before passing in the download_data() method.")
            return

        response.raise_for_status() 
        return response.json() 
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Invalid Token. Please Login and Try Again.\nError Details: {e}")
        if generate_logs:
            logger.error("[ERROR] Invalid Token Error encountered. Please Login Successfully and Try Again.\nError Details: ", exc_info=True)
        return None

def logout():
    data = {"username":username} 
    retry_delays = [5, 10, 20, 30, 40, 50] # Total Retry Time: 155 Seconds (2.5 mins)

    for attempt, delay in enumerate(retry_delays):
        try:
            response = requests.post(logout_url, json=data, timeout=5)

            if response.status_code == 400:
                resp = response.json()
                err_msg = resp['error']
                print(f"\n[ERROR] Validation Error: {err_msg}\n")
                if generate_logs:
                    logger.error(f"There was an Error encountered regarding the Validation of 'username' in Logout.\nError Details: {err_msg}\nSolution: Please make sure you use the Correct Username associated with your MOSDAC account.")
                return

            response.raise_for_status()
            print(f"\nLogout Successful. {BOLD}Goodbye {username}!{RESET}\n")
            return

        except (requests.ConnectionError, requests.Timeout, OSError):
            if attempt < len(retry_delays) - 1:
                print(f"\n[WARNING] Network Error encountered during Logout. Please check your Internet Connection.")
                print(f"[INFO] Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("Logout Failed after Multiple Attempts due to Network Error. Please check your Internet connection and Try Again.\n")
                if generate_logs:
                    logger.error("Logout could not be successful even after Multiple Attempts due to the encountered Network Error. Please check your Internet and Try Again to successfully Terminate your session.")
                return

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Error encountered in logout()", e)
            if generate_logs:
                logger.error(f"Error Encountered during Logout | Error Details: ", exc_info=True)
        

def main():

    total_files = search_results()  
    user_response = get_user_input()

    # Ending Script if User Response = No
    if user_response == 'n' or user_response == 'no':
        print(f"\n{GREEN}Download Cancelled.{RESET}")
        return
    else:
        print("\nVerifying User Credentials..")

    # Step 2: Login if Prompted for Download Data
    result = get_token()
    if result is None: 
        exit()
    else:
        tokens, username = result

    if tokens:
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token") 

        print(f"\n{GREEN}Login Successful.{RESET} {BOLD}Hello {username}!{RESET}")
    else:
        if generate_logs:
            logger.error("User could not be Authenticated, thus did not Proceed with Download.")
        print("User Authentication Failure, hence cannot Proceed with Download.")
        return

    start_time = time.time()

    download_complete, download_count, skip_count = fetch_and_download_data(total_files, access_token, refresh_token)
    
    end_time = time.time()

    if download_complete:
        print(f"\n{GREEN}Download Complete!{RESET}\n")
        total_time = end_time - start_time
        total_minutes = total_time / 60
        total_hours = total_time / 3600

        print(f"Total No. of Files Downloaded: {download_count}") 

        if (skip_count > 1):
            print(f"Files Skipped for Download: {skip_count}\n") 
        
        if total_hours >= 1:
            print(f"Total Time Taken: {total_hours:.2f} hr")
        elif total_minutes >= 1:
            print(f"Total Time Taken: {total_minutes:.2f} min")
        else:
            print(f"Total Time Taken: {total_time:.2f} sec")
    
    logout()

if __name__ == "__main__":
    main()

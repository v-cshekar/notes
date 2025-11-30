"""
sonic_warmreboot_blocker_checker.py

This net task runs version-specific scripts that contain readonly commands to
detect if the next warm-reboot operation would abort due to unsafe device state.
The results of the checks are written to a JSON file on the device, parsed, and
used to determine task success or failure. Scripts are selected based on the
device's SONiC OS version.

"""

import os
import logging
import re
import json
import glob
import datetime
import getpass
import fcm_operations
import net_devices2
import netmiko
from net_devices2.drivers import SonicBase
from net_task import app, read_write
from net_task.utilites import log_results_kusto

TASK_NAME = "sonic_warmreboot_blocker_checker"

# Expected success message in script output
MISSING_FILE_ERROR = "No such file or directory"

# JSON output file path on device
EXIT_CHECK_RESULTS_JSON = "/tmp/exit_check_validation_results.json"

# Base directory for locating scripts
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_FOLDER = "sonic_warmreboot_blocker_checker"

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def build_version_script_map():
    """
    Dynamically build VERSION_SCRIPT_MAP by scanning the script directory.
    Looks for files matching pattern: exit_check_<version>.sh

    :return: Dictionary mapping version strings to script filenames
    :rtype: dict
    """
    version_map = {}
    script_dir = os.path.join(BASE_DIR, "changes", SCRIPT_FOLDER)
    pattern = os.path.join(script_dir, "exit_check_*.sh")
    for script_path in glob.glob(pattern):
        filename = os.path.basename(script_path)
        # Extract version from filename: exit_check_202405.sh -> 202405
        match = re.search(r"exit_check_(\d{6})\.sh", filename)
        if match:
            version = match.group(1)
            version_map[version] = filename
            logger.info(f"Found script mapping: {version} -> {filename}")
    return version_map


# Script configuration mapping - Dynamically populated from script directory
VERSION_SCRIPT_MAP = build_version_script_map()

if VERSION_SCRIPT_MAP:
    logger.info(f"Loaded exit check scripts for {len(VERSION_SCRIPT_MAP)} versions: {sorted(VERSION_SCRIPT_MAP.keys())}")
else:
    script_dir = os.path.join(BASE_DIR, "changes", SCRIPT_FOLDER)
    logger.warning(f"No exit check scripts found in {script_dir}. Check if the script directory exists and contains exit_check_*.sh files.")

# FCM Configuration
CHANGE_DURATION_IN_MINS = 3
CHANGE_START = str(datetime.datetime.now().replace(microsecond=0))
CHANGE_END = str(datetime.datetime.now().replace(microsecond=0) + datetime.timedelta(minutes=CHANGE_DURATION_IN_MINS))
CHANGE_RISK = "Low"
CHANGE_ICM = "711199096"  # Update with actual ICM number


def log_results(device_name, requestid, msg):
    """Log informational messages"""
    logger.info(msg)
    log_results_kusto(device_name, TASK_NAME, requestid, msg)


def log_info(device_name, request_id, msg):
    """Log info level messages"""
    logger.info(f"On {device_name} for {request_id}: {msg}")


def log_results_err(device_name, requestid, msg):
    """Log error messages"""
    logger.error(msg)
    log_results_kusto(device_name, TASK_NAME, requestid, msg)


def extract_version_from_os_version(os_version_string):
    """
    Extract the version number from SONiC OS version string.

    Examples:
        "SONiC.20181130.101" -> "201811"
        "SONiC.20230531.01" -> "202305"

    :param os_version_string: OS version string from device
    :type os_version_string: str
    :return: Extracted version string (e.g., "201811", "202305")
    :rtype: str or None
    """
    # Pattern to match 6-digit version numbers like 201811, 202305, etc.
    pattern = r"(\d{6})"
    match = re.search(pattern, os_version_string)
    if match:
        return match.group(1)
    return None


def validate_device_and_get_version(handler, device_name, requestid):
    """
    Verify device is SONiC and extract OS version.

    :param handler: net_devices2 handler object
    :type handler: net_devices2 handler object
    :param device_name: name of the device
    :type device_name: str
    :param requestid: request ID for tracking
    :type requestid: str
    :return: Tuple of (is_valid, version_key) where version_key is like "201811"
    :rtype: tuple(bool, str or None)
    """
    if not isinstance(handler, SonicBase):
        log_results(
            device_name,
            requestid,
            "Unexpected device OS type. Only SONiC is supported.",
        )
        return False, None

    # Version check: try to fetch from device CLI then fallback to NGS/Kusto
    os_version = ""
    try:
        os_version = handler.running_os_version
    except Exception:
        logger.exception(f"Failed to get the running OS version of the device, using kusto data")
        os_version = handler.os_version

    log_info(device_name, requestid, f"Device OS version detected: {os_version}")

    version_key = extract_version_from_os_version(os_version)
    if not version_key:
        log_results_err(
            device_name,
            requestid,
            f"Unable to parse version from OS version string: {os_version}",
        )
        return False, None

    if version_key not in VERSION_SCRIPT_MAP:
        log_results_err(
            device_name,
            requestid,
            f"Unsupported OS version: {version_key}. Supported versions: {list(VERSION_SCRIPT_MAP.keys())}",
        )
        return False, None

    log_info(device_name, requestid, f"Matched version key: {version_key}")
    return True, version_key


def select_script_for_version(version_key, device_name, requestid):
    """
    Select the appropriate script based on OS version.

    :param version_key: Version key like "201811", "202305"
    :type version_key: str
    :param device_name: name of the device
    :type device_name: str
    :param requestid: request ID for tracking
    :type requestid: str
    :return: Script filename
    :rtype: str
    """
    script_filename = VERSION_SCRIPT_MAP.get(version_key)
    if not script_filename:
        log_results_err(
            device_name,
            requestid,
            f"No script mapping found for version: {version_key}",
        )
        return None

    log_info(device_name, requestid, f"Selected script: {script_filename}")

    return script_filename


def scp_files_to_device(handler, local_files, target_dir):
    """ Transfer local file to handler.device_name

        Args:
            handler (obj): net_devices2 handler
            local_files (list): files to transfer
            target_dir (str): target directory on device
    """
    if not target_dir.endswith("/"):
        target_dir += "/"

    for local_file in local_files:
        if "/" in local_file:
            filename = local_file.split("/")[-1]
        else:
            filename = local_file

        scp_connection = netmiko.SCPConn(handler.connection)
        scp_connection.scp_put_file(local_file, f"{target_dir}{filename}")
        logger.info(f"Successfully transferred {filename}")


def parse_exit_check_results(handler, device_name, requestid):
    """
    Read and parse the exit check results JSON file from the device.

    :param handler: net_devices2 handler object
    :type handler: net_devices2 handler object
    :param device_name: name of the device
    :type device_name: str
    :param requestid: request ID for tracking
    :type requestid: str
    :return: Tuple of (success, results_dict)
    :rtype: tuple(bool, dict)
    """
    try:
        # Read the JSON results file
        log_info(device_name, requestid, f"Reading results from {EXIT_CHECK_RESULTS_JSON}")
        cat_cmd = f"sudo cat {EXIT_CHECK_RESULTS_JSON}"
        json_output = handler.connection.send_command(cat_cmd)

        if not json_output or MISSING_FILE_ERROR in json_output:
            log_results_err(
                device_name,
                requestid,
                f"Results file not found: {EXIT_CHECK_RESULTS_JSON}",
            )
            return False, {}

        # Strip command echo and find actual JSON content
        json_start = json_output.find('{')
        if json_start != -1:
            json_output = json_output[json_start:].strip()

        # Parse JSON
        try:
            results = json.loads(json_output)
            log_info(
                device_name,
                requestid,
                f"Parsed results: {json.dumps(results, indent=2)}",
            )

            # Extract key fields
            overall_status = results.get("overall_status", "UNKNOWN")
            total_failures = results.get("total_failures", 0)
            failed_validations = results.get("failed_validations", [])
            timestamp = results.get("timestamp", "N/A")

            # Log summary
            log_results(
                device_name,
                requestid,
                f"Exit check results - Status: {overall_status}, Total Failures: {total_failures}, Timestamp: {timestamp}",
            )

            # Log failure details if any
            if overall_status == "FAILED" and failed_validations:
                failure_details = "\n".join([f"  - Exit Code {v.get('exit_code')}: {v.get('message')}" for v in failed_validations])
                log_results_err(
                    device_name,
                    requestid,
                    f"Exit check failed with {total_failures} failure(s):\n{failure_details}",
                )

            return overall_status == "PASSED", results

        except json.JSONDecodeError as e:
            log_results_err(
                device_name,
                requestid,
                f"Failed to parse JSON results: {e}. Raw output: {json_output}",
            )
            return False, {}

    except Exception as e:
        log_results_err(device_name, requestid, f"Failed to read results file: {e}")
        return False, {}


def run_bash_script(handler, device_name, requestid, script_filename):
    """
    Execute the bash script on the device and parse JSON results.

    :param handler: net_devices2 handler object
    :type handler: net_devices2 handler object
    :param device_name: name of the device
    :type device_name: str
    :param requestid: request ID for tracking
    :type requestid: str
    :param script_filename: Name of the script file to execute
    :type script_filename: str
    :return: True if successful, False otherwise
    :rtype: bool
    """
    try:
        script_path = f"/tmp/{script_filename}"
        common_script_path = "/tmp/exit_check_common.sh"

        # Make script executable
        chmod_cmd = f"sudo chmod +x {script_path}"
        log_info(device_name, requestid, f"Making script executable")
        handler.connection.send_command(chmod_cmd)

        # Make common script executable
        chmod_common_cmd = f"sudo chmod +x {common_script_path}"
        log_info(device_name, requestid, f"Making common script executable")
        handler.connection.send_command(chmod_common_cmd)

        # Remove any existing results file
        remove_results_cmd = f"sudo rm -f {EXIT_CHECK_RESULTS_JSON}"
        log_info(device_name, requestid, f"Removing old results file if exists")
        handler.connection.send_command(remove_results_cmd)

        # Execute the script
        bash_command = f"sudo bash {script_path}"
        log_info(device_name, requestid, f"Executing bash script: {bash_command}")

        # Allow longer timeout for script execution
        script_result = handler.connection.send_command(
            bash_command,
            max_loops=600,  # Maximum loops to wait for command completion
            delay_factor=10,  # Delay multiplier for command execution
        )

        log_info(device_name, requestid, f"Script output: {script_result}")

    except Exception as e:
        log_results_err(device_name, requestid, f"Executing bash script failed with exception: {e}")
        # Continue to parse results file to determine actual outcome

    # Parse JSON results file
    success, results = parse_exit_check_results(handler, device_name, requestid)

    if success:
        # Send detailed success results to Kusto
        if results:
            log_results(
                device_name,
                requestid,
                f"Bash script {script_filename} successfully completed with PASSED status. Results: {json.dumps(results)}",
            )
        else:
            logger.info(f"Bash script {script_filename} successfully completed with PASSED status")
        return True
    else:

        logger.info(f"Bash script {script_filename} completed with FAILED status")
        if results:
            log_results_err(
                device_name,
                requestid,
                f"Bash script {script_filename} completed with FAILED status. Results: {json.dumps(results)}",
            )
        else:
            log_results_err(
                device_name,
                requestid,
                f"Bash script {script_filename} completed with FAILED status",
            )
        return False


def cleanup_script(handler, device_name, requestid, script_filename):
    """
    Clean up the script file and results JSON from the device after execution.

    :param handler: net_devices2 handler object
    :type handler: net_devices2 handler object
    :param device_name: name of the device
    :type device_name: str
    :param requestid: request ID for tracking
    :type requestid: str
    :param script_filename: Name of the script file to remove
    :type script_filename: str
    """
    try:
        # Clean up script file
        script_path = f"/tmp/{script_filename}"
        remove_script_cmd = f"sudo rm -f {script_path}"
        log_info(device_name, requestid, f"Cleaning up script: {remove_script_cmd}")
        handler.connection.send_command(remove_script_cmd)

        # Clean up common script file
        common_script_path = "/tmp/exit_check_common.sh"
        remove_common_script_cmd = f"sudo rm -f {common_script_path}"
        log_info(device_name, requestid, f"Cleaning up common script: {remove_common_script_cmd}")
        handler.connection.send_command(remove_common_script_cmd)

        # Clean up results JSON file
        remove_json_cmd = f"sudo rm -f {EXIT_CHECK_RESULTS_JSON}"
        log_info(device_name, requestid, f"Cleaning up results file: {remove_json_cmd}")
        handler.connection.send_command(remove_json_cmd)

        log_info(
            device_name,
            requestid,
            f"Successfully cleaned up {script_filename}, exit_check_common.sh and results file",
        )
    except Exception as e:
        log_results_err(device_name, requestid, f"Failed to cleanup files: {e}")


def create_fcm_entry(
    device,
    task_name,
    icm_number,
    change_start_time,
    change_finish_time,
    requestid,
    state="ChangeInProcess",
):
    """
    Create an FCM (Firewall Change Management) entry.

    :param device: device name
    :type device: str
    :param task_name: name of the task
    :type task_name: str
    :param icm_number: ICM ticket number
    :type icm_number: str
    :param change_start_time: change start timestamp
    :type change_start_time: str
    :param change_finish_time: change end timestamp
    :type change_finish_time: str
    :param requestid: request ID
    :type requestid: str
    :param state: FCM state, defaults to "ChangeInProcess"
    :type state: str
    :return: True if FCM entry created successfully
    :rtype: bool
    """

    fcm_client = fcm_operations.FcmApi()
    is_fcm_entry_created = fcm_client.new_change_entry(
        device,
        title=f"{task_name} - Warm Reboot Blocker Check",
        description="Execute version-specific exit check scripts to validate warm-reboot readiness",
        start_time=change_start_time,
        finish_time=change_finish_time,
        risk=CHANGE_RISK,
        icm_number=icm_number,
        username=getpass.getuser(),
        service_name="PhyNet\\Change Management",
        change_status=state,
    )

    if not is_fcm_entry_created:
        msg = f"Failed to create FCM entry for device:{device}." f" task_name:{task_name}"
        log_results_err(device, requestid, msg)

    return is_fcm_entry_created


@read_write
@app.task(bind=True)
def execute_sonic_warmreboot_blocker_checker(self, device_name: str, read_write: bool = True):
    """
    Main task to execute version-specific warm-reboot blocker check scripts on SONiC devices.

    :param device_name: name of the device to run the script on
    :type device_name: str
    :param read_write: sets read_write flag, defaults to True
    :type read_write: bool
    :return: True for task success, False for failure
    :rtype: bool
    """
    try:
        log_info(
            device_name,
            self.request.id,
            f"Starting {TASK_NAME} for device {device_name}",
        )

        # Get device handler and connect
        handler = net_devices2.get_device_handler(device_name)
        handler.connect(read_write=read_write)

        # Validate device and get version
        is_valid, version_key = validate_device_and_get_version(handler, device_name, self.request.id)
        if not is_valid:
            log_results_kusto(
                device_name,
                TASK_NAME,
                self.request.id,
                "Device validation failed or unsupported version",
            )
            return False

        # Select script for the version
        script_filename = select_script_for_version(version_key, device_name, self.request.id)
        if not script_filename:
            log_results_kusto(
                device_name,
                TASK_NAME,
                self.request.id,
                "Failed to select appropriate script",
            )
            return False

        # Create FCM entry
        fcm_entry_created = create_fcm_entry(
            device_name,
            TASK_NAME,
            CHANGE_ICM,
            CHANGE_START,
            CHANGE_END,
            self.request.id,
            state="ChangeInProcess",
        )

        # Transfer script to device
        script_path = os.path.join(BASE_DIR, "changes", SCRIPT_FOLDER)
        source_path = os.path.join(script_path, script_filename)
        common_script_path = os.path.join(script_path, "exit_check_common.sh")

        # Check if source script exists
        if not os.path.exists(source_path):
            log_results_err(device_name, self.request.id, f"Script file not found at: {source_path}")
            return False

        # Check if common script exists
        if not os.path.exists(common_script_path):
            log_results_err(device_name, self.request.id, f"Common script file not found at: {common_script_path}")
            return False

        # Remove any existing scripts
        scp_target_path = os.path.join("/tmp", script_filename)
        remove_bash_script_cmd = f"sudo rm -f {scp_target_path}"
        handler.connection.send_command(remove_bash_script_cmd)

        common_scp_target_path = os.path.join("/tmp", "exit_check_common.sh")
        remove_common_script_cmd = f"sudo rm -f {common_scp_target_path}"
        handler.connection.send_command(remove_common_script_cmd)

        try:
            scp_files_to_device(handler, [source_path, common_script_path], "/tmp")
            logger.info(f"Successfully transferred {script_filename} and exit_check_common.sh to device")
        except Exception as e:
            log_results_err(device_name, self.request.id, f"SCP transfer failed with exception: {e}")
            return False

        # Execute script
        execution_success = run_bash_script(handler, device_name, self.request.id, script_filename)

        # Clean up script file
        cleanup_script(handler, device_name, self.request.id, script_filename)

        # Create a COMPLETED FCM entry as there are no more read write operations
        try:
            if fcm_entry_created:
                create_fcm_entry(
                    device_name,
                    TASK_NAME,
                    CHANGE_ICM,
                    CHANGE_START,
                    CHANGE_END,
                    self.request.id,
                    state="Completed",
                )
                logger.info(f"Completion FCM entry created for device:{device_name}. task_name:{TASK_NAME}")
            else:
                logger.info(f"FCM entry was not created for device:{device_name}. task_name:{TASK_NAME}. Ignore closing of FCM entry")
        except Exception as e:
            logger.exception(f"Exception hit closing FCM entry: {device_name}: {e}")

        # Log final result
        if execution_success:
            log_results_kusto(
                device_name,
                TASK_NAME,
                self.request.id,
                f"Successfully executed {script_filename} for version {version_key}",
            )
            return True
        else:
            log_results_kusto(
                device_name,
                TASK_NAME,
                self.request.id,
                f"Failed to execute {script_filename}",
            )
            return False

    except Exception as e:
        logger.exception(f"{device_name}, {TASK_NAME}, {self.request.id} failed with exception: {e}")
        log_results_kusto(device_name, TASK_NAME, self.request.id, f"Task failed with exception: {e}")
        return False
    finally:
        try:
            if handler:
                handler.disconnect()
        except Exception:
            pass

"""
Standalone script to reproduce the JSON parsing issue in sonic_warmreboot_blocker_checker.py
"""

import json
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Constants
TASK_NAME = "sonic_warmreboot_blocker_checker"
EXIT_CHECK_RESULTS_JSON = "/tmp/exit_check_validation_results.json"
MISSING_FILE_ERROR = "No such file or directory"


def log_info(device_name, request_id, msg):
    """Log info level messages"""
    logger.info(f"On {device_name} for {request_id}: {msg}")


def log_results(device_name, requestid, msg):
    """Log informational messages"""
    logger.info(msg)


def log_results_err(device_name, requestid, msg):
    """Log error messages"""
    logger.error(msg)


# Mock handler class that simulates network device behavior
class MockConnection:
    def __init__(self, output_with_echo=True):
        self.output_with_echo = output_with_echo

    def send_command(self, cmd):
        """Simulate device output - with or without command echo"""
        json_content = """{
  "timestamp": "2025-11-18 22:54:32 UTC",
  "overall_status": "FAILED",
  "total_failures": 1,
  "failed_exit_codes": [30],
  "failed_validations": [
    {"exit_code": 30, "message": "Leftover CPA tunnel configuration detected"}
  ]
}"""

        if self.output_with_echo:
            # This simulates what actually comes back from a network device
            # It includes the command prompt and command echo
            return f"dsm06-0102-0317-03t0# {cmd}\n{json_content}"
        else:
            # Clean output (just the JSON)
            return json_content


class MockHandler:
    def __init__(self, with_echo=True):
        self.connection = MockConnection(output_with_echo=with_echo)


def parse_exit_check_results(handler, device_name, requestid):
    """
    Read and parse the exit check results JSON file from the device.
    This is the ORIGINAL function that has the bug.
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
            if total_failures > 0:
                failure_details = "\n".join(
                    [f"  - Exit code {v['exit_code']}: {v['message']}" for v in failed_validations]
                )
                log_results(
                    requestid,
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


def main():
    """Test the function with both scenarios"""

    print("=" * 80)
    print("TEST 1: With command echo (BUGGY - will fail)")
    print("=" * 80)
    handler_with_echo = MockHandler(with_echo=True)

    # Show what the handler returns
    print("\nRaw output from handler.connection.send_command():")
    print(repr(handler_with_echo.connection.send_command("sudo cat /tmp/exit_check_validation_results.json")))
    print()

    success, results = parse_exit_check_results(handler_with_echo, "dsm06-0102-0317-03t0", "None")
    print(f"\nResult: success={success}, results={results}")

    print("\n" + "=" * 80)
    print("TEST 2: Without command echo (WORKS)")
    print("=" * 80)
    handler_without_echo = MockHandler(with_echo=False)

    # Show what the handler returns
    print("\nRaw output from handler.connection.send_command():")
    print(repr(handler_without_echo.connection.send_command("sudo cat /tmp/exit_check_validation_results.json")))
    print()

    success, results = parse_exit_check_results(handler_without_echo, "dsm06-0102-0317-03t0", "None")
    print(f"\nResult: success={success}, results={results}")


if __name__ == "__main__":
    main()

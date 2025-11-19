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



parse_exit_check_results



  # Strip command echo and find actual JSON content
  json_start = json_output.find('{')
  if json_start != -1:
      json_output = json_output[json_start:].strip()



INFO: On dsm06-0102-0317-03t0 for None: Reading results from /tmp/exit_check_validation_results.json
ERROR: Failed to parse JSON results: Expecting value: line 1 column 1 (char 0). Raw output: dsm06-0102-0317-03t0# cat /tmp/exit_check_validation_results.json

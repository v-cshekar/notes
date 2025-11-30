#!/bin/bash -e

# Shared library for exit check validation scripts
# This file contains common infrastructure, logging, and result reporting functions
# 
# Each exit_check_*.sh script should:
#   1. Source this file: source "${SCRIPT_DIR}/exit_check_common.sh"
#   2. Define version-specific EXIT_* constants
#   3. Define the ERROR_CONSTANTS array listing all error constants
#   4. Define version-specific check_exit_* functions
#   5. Implement main() to orchestrate the validation calls

# Common utility functions used by all exit_check_*.sh scripts

function error()
{
    # Print to stderr with standardized format for Kusto ingestion
    echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S UTC') $@" >&2
}

function debug()
{
    # Print to stdout with standardized format for Kusto ingestion
    echo "[DEBUG] $(date '+%Y-%m-%d %H:%M:%S UTC') $@"
}

function get_error_message()
{
    # Get error message by exit code using the reverse lookup array
    local exit_code="$1"
    echo "${EXIT_CHECK_ERROR_MESSAGES[$exit_code]:-Unknown error code: $exit_code}"
}

function report_validation_failure()
{
    # Report validation failure with structured format for Kusto
    local exit_code="$1"
    local message="${EXIT_CHECK_ERROR_MESSAGES[$exit_code]:-Unknown error code: $exit_code}"
    echo "[RESULT] VALIDATION_FAILED: $exit_code - $message"
}

function write_json_results()
{
    # Write validation results to JSON file
    # This function handles both success and failure cases
    # Parameters:
    #   $1 = overall_status ("PASSED" or "FAILED")
    #   For "PASSED": only pass status
    #   For "FAILED": pass status, then failed_exit_codes (as array elements), then failed_messages (as array elements)
    
    local overall_status="$1"
    local JSON_FILE="/tmp/exit_check_validation_results.json"
    local TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S UTC')
    
    if [[ "$overall_status" == "PASSED" ]]; then
        # Create JSON structure for success case
        echo "{" > "$JSON_FILE"
        echo "  \"timestamp\": \"$TIMESTAMP\"," >> "$JSON_FILE"
        echo "  \"overall_status\": \"PASSED\"," >> "$JSON_FILE"
        echo "  \"total_failures\": 0," >> "$JSON_FILE"
        echo "  \"failed_exit_codes\": []," >> "$JSON_FILE"
        echo "  \"failed_validations\": []" >> "$JSON_FILE"
        echo "}" >> "$JSON_FILE"
    else
        # For FAILED case, the caller should pass failed_exit_codes and failed_messages arrays
        # This is handled by the caller who has access to these arrays
        : # Placeholder - actual FAILED case is handled differently by each script
    fi
}

function write_json_results_failed()
{
    # Write validation results to JSON file for failure case
    # This function is called with arrays of failed exit codes and messages
    # Parameters:
    #   $1 = number of failures
    #   $2+ = array of failed exit codes
    #   (the messages should be looked up from EXIT_CHECK_ERROR_MESSAGES)
    
    local num_failures="$1"
    shift
    local failed_exit_codes=("$@")
    local JSON_FILE="/tmp/exit_check_validation_results.json"
    local TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S UTC')

    # Create JSON structure
    # Join array elements with commas for valid JSON format
    local codes_str=$(IFS=','; echo "${failed_exit_codes[*]}")
    echo "{" > "$JSON_FILE"
    echo "  \"timestamp\": \"$TIMESTAMP\"," >> "$JSON_FILE"
    echo "  \"overall_status\": \"FAILED\"," >> "$JSON_FILE"
    echo "  \"total_failures\": ${num_failures}," >> "$JSON_FILE"
    echo "  \"failed_exit_codes\": [${codes_str}]," >> "$JSON_FILE"
    echo "  \"failed_validations\": [" >> "$JSON_FILE"
    
    # Add each failed validation as JSON object
    for i in "${!failed_exit_codes[@]}"; do
        local exit_code="${failed_exit_codes[$i]}"
        local message="${EXIT_CHECK_ERROR_MESSAGES[$exit_code]:-Unknown error}"
        echo -n "    {\"exit_code\": ${exit_code}, \"message\": \"${message}\"}" >> "$JSON_FILE"
        if [ $i -lt $((${#failed_exit_codes[@]} - 1)) ]; then
            echo "," >> "$JSON_FILE"
        else
            echo "" >> "$JSON_FILE"
        fi
    done
    
    echo "  ]" >> "$JSON_FILE"
    echo "}" >> "$JSON_FILE"
}


def make_single_case_report(
    command: str,
    status: str,
    input_file: str | None,
    output_file: str | None,
    error_type: str | None,
    prompt_hash: str | None = None,
    include_prompt_hash: bool = False,
) -> dict:
    success_count = 1 if status == "SUCCESS" else 0
    diff_count = 1 if status == "DIFF" else 0
    error_count = 1 if status == "ERROR" else 0
    failure_count_by_type: dict[str, int] = {}
    if error_type is not None:
        failure_count_by_type[error_type] = 1
    case = {
        "case_id": "case_0",
        "status": status,
        "input_file": input_file,
        "output_file": output_file,
        "error_type": error_type,
    }
    if include_prompt_hash:
        case["prompt_hash"] = prompt_hash
    return {
        "command": command,
        "summary": {
            "total_cases": 1,
            "success_count": success_count,
            "error_count": error_count,
            "diff_count": diff_count,
            "failure_count_by_type": failure_count_by_type,
        },
        "cases": [case],
    }

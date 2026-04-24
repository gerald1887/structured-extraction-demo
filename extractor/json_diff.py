def _escape_json_pointer_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _json_pointer(path: str, token: str) -> str:
    if path == "/":
        return "/" + _escape_json_pointer_token(token)
    return path + "/" + _escape_json_pointer_token(token)


def _compare_at_path(actual: object, expected: object, path: str, out: list[dict]) -> None:
    if isinstance(actual, dict) and isinstance(expected, dict):
        keys = sorted(set(expected.keys()) | set(actual.keys()))
        for key in keys:
            key_path = _json_pointer(path, key)
            in_expected = key in expected
            in_actual = key in actual
            if in_expected and not in_actual:
                out.append({"category": "missing", "path": key_path, "expected": expected[key], "actual": None})
            elif in_actual and not in_expected:
                out.append({"category": "extra", "path": key_path, "expected": None, "actual": actual[key]})
            else:
                _compare_at_path(actual[key], expected[key], key_path, out)
        return

    if isinstance(actual, list) and isinstance(expected, list):
        min_len = min(len(actual), len(expected))
        for i in range(min_len):
            idx_path = f"{path}/{i}" if path != "/" else f"/{i}"
            _compare_at_path(actual[i], expected[i], idx_path, out)
        for i in range(min_len, len(expected)):
            idx_path = f"{path}/{i}" if path != "/" else f"/{i}"
            out.append({"category": "missing", "path": idx_path, "expected": expected[i], "actual": None})
        for i in range(min_len, len(actual)):
            idx_path = f"{path}/{i}" if path != "/" else f"/{i}"
            out.append({"category": "extra", "path": idx_path, "expected": None, "actual": actual[i]})
        return

    if actual != expected:
        out.append({"category": "mismatch", "path": path, "expected": expected, "actual": actual})


def compare_json(actual: object, expected: object) -> list[dict]:
    diffs: list[dict] = []
    _compare_at_path(actual, expected, "/", diffs)
    return diffs


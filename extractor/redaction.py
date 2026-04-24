import copy
import json
import re
from pathlib import Path
from typing import Any

from extractor.errors import AppError, INTERNAL_ERROR


def load_redaction_config(path: str) -> dict:
    try:
        raw = Path(path).read_text(encoding="utf-8")
        config = json.loads(raw)
    except Exception as exc:
        raise AppError(INTERNAL_ERROR, "Invalid redaction config") from exc
    if not isinstance(config, dict):
        raise AppError(INTERNAL_ERROR, "Invalid redaction config")
    rules = config.get("rules")
    if not isinstance(rules, list):
        raise AppError(INTERNAL_ERROR, "Invalid redaction config")
    for rule in rules:
        _validate_rule(rule)
    return config


def apply_redaction(data: dict, config: dict) -> dict:
    value = copy.deepcopy(data)
    for rule in config["rules"]:
        value = _apply_rule(value, rule)
    return value


def _validate_rule(rule: Any) -> None:
    if not isinstance(rule, dict):
        raise AppError(INTERNAL_ERROR, "Invalid redaction rule")
    match_type = rule.get("match_type")
    action = rule.get("action")
    if match_type not in {"exact_key", "json_pointer", "regex_replace"}:
        raise AppError(INTERNAL_ERROR, "Invalid redaction rule")
    if action not in {"mask", "remove_field", "replace_constant"}:
        raise AppError(INTERNAL_ERROR, "Invalid redaction rule")
    if match_type == "exact_key" and "key" not in rule:
        raise AppError(INTERNAL_ERROR, "Invalid redaction rule")
    if match_type == "json_pointer" and "pointer" not in rule:
        raise AppError(INTERNAL_ERROR, "Invalid redaction rule")
    if match_type == "regex_replace":
        pattern = rule.get("pattern")
        if not isinstance(pattern, str):
            raise AppError(INTERNAL_ERROR, "Invalid redaction rule")
        if action == "remove_field":
            raise AppError(INTERNAL_ERROR, "Invalid redaction rule")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise AppError(INTERNAL_ERROR, "Invalid regex pattern") from exc
    if action == "replace_constant" and "value" not in rule:
        raise AppError(INTERNAL_ERROR, "Invalid redaction rule")


def _apply_rule(data: Any, rule: dict) -> Any:
    match_type = rule["match_type"]
    if match_type == "exact_key":
        return _apply_exact_key(data, rule)
    if match_type == "json_pointer":
        return _apply_json_pointer(data, rule)
    return _apply_regex_replace(data, rule)


def _apply_exact_key(data: Any, rule: dict) -> Any:
    key = rule["key"]
    action = rule["action"]
    if isinstance(data, dict):
        out: dict[str, Any] = {}
        for current_key in sorted(data.keys()):
            value = _apply_exact_key(data[current_key], rule)
            if current_key != key:
                out[current_key] = value
                continue
            if action == "remove_field":
                continue
            out[current_key] = _replacement_value(rule)
        return out
    if isinstance(data, list):
        return [_apply_exact_key(item, rule) for item in data]
    return data


def _apply_json_pointer(data: Any, rule: dict) -> Any:
    pointer = rule["pointer"]
    if pointer == "":
        if rule["action"] == "remove_field":
            return data
        return _replacement_value(rule)
    tokens = [_decode_pointer_token(token) for token in pointer.lstrip("/").split("/")]
    clone = copy.deepcopy(data)
    _apply_pointer_mutation(clone, tokens, rule)
    return clone


def _apply_pointer_mutation(root: Any, tokens: list[str], rule: dict) -> None:
    parent = root
    for token in tokens[:-1]:
        if isinstance(parent, dict):
            if token not in parent:
                return
            parent = parent[token]
            continue
        if isinstance(parent, list):
            if not token.isdigit():
                return
            idx = int(token)
            if idx < 0 or idx >= len(parent):
                return
            parent = parent[idx]
            continue
        return
    last = tokens[-1]
    if isinstance(parent, dict):
        if last not in parent:
            return
        if rule["action"] == "remove_field":
            del parent[last]
            return
        parent[last] = _replacement_value(rule)
        return
    if isinstance(parent, list):
        if not last.isdigit():
            return
        idx = int(last)
        if idx < 0 or idx >= len(parent):
            return
        if rule["action"] == "remove_field":
            del parent[idx]
            return
        parent[idx] = _replacement_value(rule)


def _apply_regex_replace(data: Any, rule: dict) -> Any:
    pattern = re.compile(rule["pattern"])
    action = rule["action"]
    if isinstance(data, dict):
        out: dict[str, Any] = {}
        for key in sorted(data.keys()):
            out[key] = _apply_regex_replace(data[key], rule)
        return out
    if isinstance(data, list):
        return [_apply_regex_replace(item, rule) for item in data]
    if isinstance(data, str) and pattern.search(data):
        if action == "mask":
            return rule.get("mask_value", "***")
        if action == "replace_constant":
            return rule["value"]
    return data


def _replacement_value(rule: dict) -> Any:
    action = rule["action"]
    if action == "mask":
        return rule.get("mask_value", "***")
    if action == "replace_constant":
        return rule["value"]
    return None


def _decode_pointer_token(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")

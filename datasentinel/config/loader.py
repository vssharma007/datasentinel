"""Configuration loader with environment variable interpolation."""

import os
import re
from pathlib import Path
from typing import Any, Dict, Union
import yaml
from pydantic import ValidationError

from datasentinel.config.schema import SentinelConfig
from datasentinel.core.exceptions import ConfigurationError

ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z0-9_]+)(?::-([^}]*))?\}")


def _interpolate_env_vars(raw: str) -> str:
    """Replace ${VAR} or ${VAR:-default} with OS environment variable values."""

    def replacer(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default_val = match.group(2) if match.group(2) is not None else ""
        return os.environ.get(var_name, default_val)

    return ENV_VAR_PATTERN.sub(replacer, raw)


def _recursively_interpolate(obj: Any) -> Any:
    """Recursively interpolate string environment variables in nested structures."""
    if isinstance(obj, str):
        return _interpolate_env_vars(obj)
    if isinstance(obj, dict):
        return {k: _recursively_interpolate(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_recursively_interpolate(item) for item in obj]
    return obj


def load_config_from_yaml(path: Union[str, Path]) -> SentinelConfig:
    """Load, interpolate, and validate a SentinelConfig from a YAML file path.

    Args:
        path: Filepath to YAML rule configuration.

    Returns:
        Validated SentinelConfig instance.

    Raises:
        ConfigurationError: If the file does not exist, has syntax errors,
            or fails Pydantic schema validation.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise ConfigurationError(
            f"Configuration file not found: {file_path}",
            details="Ensure the path is correct and accessible.",
        )

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        raise ConfigurationError(
            f"Failed to read configuration file: {file_path}",
            details=str(exc),
        ) from exc

    try:
        raw_dict = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            f"YAML parsing error in {file_path}",
            details=str(exc),
        ) from exc

    if not isinstance(raw_dict, dict):
        raise ConfigurationError(
            f"Invalid configuration format in {file_path}. Expected a YAML mapping/dictionary.",
            details=f"Received: {type(raw_dict).__name__}",
        )

    interpolated_dict = _recursively_interpolate(raw_dict)
    if not isinstance(interpolated_dict, dict):
        raise ConfigurationError("Internal error during YAML interpolation")

    try:
        return SentinelConfig.model_validate(interpolated_dict)
    except ValidationError as exc:
        raise ConfigurationError(
            f"Configuration validation failed for {file_path}",
            details=str(exc),
        ) from exc


def load_config_from_dict(data: Dict[str, Any]) -> SentinelConfig:
    """Directly validate a dictionary into a SentinelConfig."""
    interpolated = _recursively_interpolate(data)
    try:
        return SentinelConfig.model_validate(interpolated)
    except ValidationError as exc:
        raise ConfigurationError(
            "Configuration validation failed",
            details=str(exc),
        ) from exc

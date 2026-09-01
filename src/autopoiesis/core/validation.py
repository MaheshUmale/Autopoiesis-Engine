"""Input validation utilities for Autopoiesis Engine public APIs.

Provides validation functions to prevent security vulnerabilities:
- Path traversal prevention
- Identifier format validation
- Channel name validation
"""

import re
from typing import Optional

# Validation patterns (fixes M-4)
SKILL_ID_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_.]{0,127}$')
AGENT_ID_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_.\-]{0,63}$')
CHANNEL_NAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_.\-]{0,127}$')
NAMESPACE_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_.]{0,63}$')

# Reserved names that cannot be used
RESERVED_SKILL_IDS = {
    "con", "prn", "aux", "nul",
    "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
    "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
}

# Maximum lengths
MAX_SKILL_ID_LENGTH = 128
MAX_AGENT_ID_LENGTH = 64
MAX_CHANNEL_NAME_LENGTH = 128
MAX_NAMESPACE_LENGTH = 64


class ValidationError(ValueError):
    """Raised when input validation fails."""
    pass


def validate_skill_id(skill_id: str) -> str:
    """Validates a skill identifier.

    Args:
        skill_id: Skill identifier to validate

    Returns:
        The validated skill_id

    Raises:
        ValidationError: If skill_id is invalid
    """
    if not skill_id:
        raise ValidationError("skill_id cannot be empty")

    if len(skill_id) > MAX_SKILL_ID_LENGTH:
        raise ValidationError(f"skill_id exceeds maximum length of {MAX_SKILL_ID_LENGTH}")

    # Check for path traversal attempts
    if ".." in skill_id or "/" in skill_id or "\\" in skill_id:
        raise ValidationError(
            f"skill_id contains path traversal characters: '{skill_id}'. "
            "Use dots (.) for namespacing instead."
        )

    # Check against reserved names (case-insensitive)
    base_name = skill_id.split(".")[0].lower()
    if base_name in RESERVED_SKILL_IDS:
        raise ValidationError(f"skill_id uses reserved name: '{base_name}'")

    # Validate pattern
    if not SKILL_ID_PATTERN.match(skill_id):
        raise ValidationError(
            f"Invalid skill_id format: '{skill_id}'. "
            "Must start with a letter, contain only alphanumeric characters, "
            "dots, or underscores, and be 1-128 characters long."
        )

    return skill_id


def validate_agent_id(agent_id: str) -> str:
    """Validates an agent identifier.

    Args:
        agent_id: Agent identifier to validate

    Returns:
        The validated agent_id

    Raises:
        ValidationError: If agent_id is invalid
    """
    if not agent_id:
        raise ValidationError("agent_id cannot be empty")

    if len(agent_id) > MAX_AGENT_ID_LENGTH:
        raise ValidationError(f"agent_id exceeds maximum length of {MAX_AGENT_ID_LENGTH}")

    # Check for path traversal or injection attempts
    if ".." in agent_id or "/" in agent_id or "\\" in agent_id:
        raise ValidationError(f"agent_id contains invalid characters: '{agent_id}'")

    if not AGENT_ID_PATTERN.match(agent_id):
        raise ValidationError(
            f"Invalid agent_id format: '{agent_id}'. "
            "Must start with a letter, contain only alphanumeric characters, "
            "dots, hyphens, or underscores, and be 1-64 characters long."
        )

    return agent_id


def validate_channel_name(channel: str) -> str:
    """Validates a channel name.

    Args:
        channel: Channel name to validate

    Returns:
        The validated channel name

    Raises:
        ValidationError: If channel name is invalid
    """
    if not channel:
        raise ValidationError("channel name cannot be empty")

    if len(channel) > MAX_CHANNEL_NAME_LENGTH:
        raise ValidationError(f"channel name exceeds maximum length of {MAX_CHANNEL_NAME_LENGTH}")

    # Check for path traversal or injection attempts
    if ".." in channel or "\\" in channel:
        raise ValidationError(f"channel name contains invalid characters: '{channel}'")

    if not CHANNEL_NAME_PATTERN.match(channel):
        raise ValidationError(
            f"Invalid channel name format: '{channel}'. "
            "Must start with a letter, contain only alphanumeric characters, "
            "dots, hyphens, or underscores, and be 1-128 characters long."
        )

    return channel


def validate_namespace(namespace: str) -> str:
    """Validates a namespace identifier.

    Args:
        namespace: Namespace to validate

    Returns:
        The validated namespace

    Raises:
        ValidationError: If namespace is invalid
    """
    if not namespace:
        raise ValidationError("namespace cannot be empty")

    if len(namespace) > MAX_NAMESPACE_LENGTH:
        raise ValidationError(f"namespace exceeds maximum length of {MAX_NAMESPACE_LENGTH}")

    if ".." in namespace or "/" in namespace or "\\" in namespace:
        raise ValidationError(f"namespace contains invalid characters: '{namespace}'")

    if not NAMESPACE_PATTERN.match(namespace):
        raise ValidationError(
            f"Invalid namespace format: '{namespace}'. "
            "Must start with a letter, contain only alphanumeric characters, "
            "dots, or underscores, and be 1-64 characters long."
        )

    return namespace

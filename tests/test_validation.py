"""Tests for input validation on public APIs (fixes M-4)."""

import pytest
from autopoiesis.core.validation import (
    validate_skill_id,
    validate_agent_id,
    validate_channel_name,
    validate_namespace,
    ValidationError,
    SKILL_ID_PATTERN,
    AGENT_ID_PATTERN,
    CHANNEL_NAME_PATTERN,
    NAMESPACE_PATTERN,
)


class TestValidateSkillId:
    """Tests for skill_id validation."""

    def test_valid_simple_id(self):
        """Simple alphanumeric ID should be valid."""
        assert validate_skill_id("my_skill") == "my_skill"

    def test_valid_dotted_id(self):
        """Dotted ID should be valid."""
        assert validate_skill_id("core.shell") == "core.shell"

    def test_valid_underscored_id(self):
        """Underscored ID should be valid."""
        assert validate_skill_id("my_skill_123") == "my_skill_123"

    def test_valid_numeric_suffix(self):
        """ID with numeric suffix should be valid."""
        assert validate_skill_id("skill123") == "skill123"

    def test_empty_id_raises(self):
        """Empty ID should raise ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_skill_id("")

    def test_path_traversal_raises(self):
        """Path traversal attempt should raise ValidationError."""
        with pytest.raises(ValidationError, match="path traversal"):
            validate_skill_id("../../etc/passwd")

    def test_forward_slash_raises(self):
        """Forward slash should raise ValidationError."""
        with pytest.raises(ValidationError, match="path traversal"):
            validate_skill_id("skill/path")

    def test_backslash_raises(self):
        """Backslash should raise ValidationError."""
        with pytest.raises(ValidationError, match="path traversal"):
            validate_skill_id("skill\\path")

    def test_double_dot_raises(self):
        """Double dot should raise ValidationError."""
        with pytest.raises(ValidationError, match="path traversal"):
            validate_skill_id("skill..path")

    def test_reserved_name_raises(self):
        """Reserved Windows name should raise ValidationError."""
        with pytest.raises(ValidationError, match="reserved"):
            validate_skill_id("con")

    def test_reserved_name_case_insensitive(self):
        """Reserved name check should be case-insensitive."""
        with pytest.raises(ValidationError, match="reserved"):
            validate_skill_id("CON")

    def test_starts_with_number_raises(self):
        """ID starting with number should raise ValidationError."""
        with pytest.raises(ValidationError, match="Invalid skill_id"):
            validate_skill_id("123skill")

    def test_special_chars_raises(self):
        """Special characters should raise ValidationError."""
        with pytest.raises(ValidationError, match="Invalid skill_id"):
            validate_skill_id("skill@id")

    def test_too_long_raises(self):
        """Excessively long ID should raise ValidationError."""
        with pytest.raises(ValidationError, match="exceeds maximum"):
            validate_skill_id("a" * 200)


class TestValidateAgentId:
    """Tests for agent_id validation."""

    def test_valid_simple_id(self):
        """Simple alphanumeric ID should be valid."""
        assert validate_agent_id("agent1") == "agent1"

    def test_valid_with_hyphen(self):
        """ID with hyphen should be valid."""
        assert validate_agent_id("my-agent") == "my-agent"

    def test_valid_with_underscore(self):
        """ID with underscore should be valid."""
        assert validate_agent_id("my_agent") == "my_agent"

    def test_valid_with_dot(self):
        """ID with dot should be valid."""
        assert validate_agent_id("agent.v1") == "agent.v1"

    def test_empty_id_raises(self):
        """Empty ID should raise ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_agent_id("")

    def test_path_traversal_raises(self):
        """Path traversal attempt should raise ValidationError."""
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_agent_id("../agent")

    def test_slash_raises(self):
        """Slash should raise ValidationError."""
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_agent_id("agent/path")

    def test_starts_with_number_raises(self):
        """ID starting with number should raise ValidationError."""
        with pytest.raises(ValidationError, match="Invalid agent_id"):
            validate_agent_id("1agent")

    def test_too_long_raises(self):
        """Excessively long ID should raise ValidationError."""
        with pytest.raises(ValidationError, match="exceeds maximum"):
            validate_agent_id("a" * 100)


class TestValidateChannelName:
    """Tests for channel name validation."""

    def test_valid_simple_name(self):
        """Simple alphanumeric name should be valid."""
        assert validate_channel_name("my_channel") == "my_channel"

    def test_valid_dotted_name(self):
        """Dotted name should be valid."""
        assert validate_channel_name("amf.agent.test") == "amf.agent.test"

    def test_valid_with_hyphen(self):
        """Name with hyphen should be valid."""
        assert validate_channel_name("my-channel") == "my-channel"

    def test_empty_name_raises(self):
        """Empty name should raise ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_channel_name("")

    def test_path_traversal_raises(self):
        """Path traversal attempt should raise ValidationError."""
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_channel_name("../channel")

    def test_backslash_raises(self):
        """Backslash should raise ValidationError."""
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_channel_name("channel\\path")

    def test_starts_with_number_raises(self):
        """Name starting with number should raise ValidationError."""
        with pytest.raises(ValidationError, match="Invalid channel"):
            validate_channel_name("1channel")

    def test_too_long_raises(self):
        """Excessively long name should raise ValidationError."""
        with pytest.raises(ValidationError, match="exceeds maximum"):
            validate_channel_name("a" * 200)


class TestValidateNamespace:
    """Tests for namespace validation."""

    def test_valid_simple_namespace(self):
        """Simple alphanumeric namespace should be valid."""
        assert validate_namespace("global") == "global"

    def test_valid_dotted_namespace(self):
        """Dotted namespace should be valid."""
        assert validate_namespace("com.example") == "com.example"

    def test_empty_namespace_raises(self):
        """Empty namespace should raise ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_namespace("")

    def test_path_traversal_raises(self):
        """Path traversal attempt should raise ValidationError."""
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_namespace("../namespace")

    def test_slash_raises(self):
        """Slash should raise ValidationError."""
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_namespace("ns/path")

    def test_starts_with_number_raises(self):
        """Namespace starting with number should raise ValidationError."""
        with pytest.raises(ValidationError, match="Invalid namespace"):
            validate_namespace("1namespace")


class TestValidationPatterns:
    """Tests for validation regex patterns."""

    def test_skill_id_pattern_compiled(self):
        """SKILL_ID_PATTERN should be compiled."""
        import re
        assert isinstance(SKILL_ID_PATTERN, re.Pattern)

    def test_agent_id_pattern_compiled(self):
        """AGENT_ID_PATTERN should be compiled."""
        import re
        assert isinstance(AGENT_ID_PATTERN, re.Pattern)

    def test_channel_name_pattern_compiled(self):
        """CHANNEL_NAME_PATTERN should be compiled."""
        import re
        assert isinstance(CHANNEL_NAME_PATTERN, re.Pattern)

    def test_namespace_pattern_compiled(self):
        """NAMESPACE_PATTERN should be compiled."""
        import re
        assert isinstance(NAMESPACE_PATTERN, re.Pattern)


class TestValidationError:
    """Tests for ValidationError exception."""

    def test_is_value_error(self):
        """ValidationError should be a ValueError subclass."""
        assert issubclass(ValidationError, ValueError)

    def test_can_be_raised(self):
        """ValidationError should be raisable."""
        with pytest.raises(ValueError):
            raise ValidationError("test error")

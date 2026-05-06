"""Base abstractions for tools."""

from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    """Base class for tools exposed to the agent runtime."""

    _TYPE_MAP = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name used by the model and registry."""
        raise NotImplementedError

    @property
    @abstractmethod
    def description(self) -> str:
        """Short tool description."""
        raise NotImplementedError

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema describing accepted parameters."""
        raise NotImplementedError

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """Execute the tool."""
        raise NotImplementedError

    def cast_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Apply simple schema-driven casts before validation."""
        schema = self.parameters
        if schema.get("type", "object") != "object":
            return params
        props = schema.get("properties", {})
        return {
            key: self._cast_value(value, props[key]) if key in props else value
            for key, value in params.items()
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate parameters against the first-stage JSON Schema subset."""
        if not isinstance(params, dict):
            return [f"parameters must be an object, got {type(params).__name__}"]

        schema = self.parameters
        if schema.get("type", "object") != "object":
            return [f"schema for {self.name} must be object"]

        errors: list[str] = []
        props = schema.get("properties", {})
        for required in schema.get("required", []):
            if required not in params:
                errors.append(f"missing required {required}")

        for key, value in params.items():
            if key in props:
                errors.extend(self._validate_value(key, value, props[key]))
        return errors

    def to_schema(self) -> dict[str, Any]:
        """Return this tool in OpenAI-compatible function schema format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def _cast_value(self, value: Any, schema: dict[str, Any]) -> Any:
        target_type = schema.get("type")
        if target_type == "string":
            return value if value is None else str(value)
        if target_type == "integer" and isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return value
        if target_type == "number" and isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return value
        if target_type == "boolean" and isinstance(value, str):
            lowered = value.lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
        return value

    def _validate_value(self, name: str, value: Any, schema: dict[str, Any]) -> list[str]:
        target_type = schema.get("type")
        expected = self._TYPE_MAP.get(target_type)
        errors: list[str] = []

        if expected is not None:
            if target_type == "integer":
                if not isinstance(value, int) or isinstance(value, bool):
                    errors.append(f"{name} should be integer")
            elif target_type == "number":
                if not isinstance(value, expected) or isinstance(value, bool):
                    errors.append(f"{name} should be number")
            elif not isinstance(value, expected):
                errors.append(f"{name} should be {target_type}")

        if errors:
            return errors

        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{name} must be >= {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{name} must be <= {schema['maximum']}")
        return errors

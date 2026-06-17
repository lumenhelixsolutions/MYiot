"""
Standardized payload schemas for Smart Home Universal Hub.

Defines Pydantic models for device-type-specific command payloads
that get translated to manufacturer-specific formats by the dispatcher.
"""

from typing import Union, Tuple, Optional
from pydantic import BaseModel, Field, field_validator


class SmartPlugPayload(BaseModel):
    """Payload schema for smart plug devices."""
    power: bool


class SmartLightPayload(BaseModel):
    """Payload schema for smart light devices."""
    power: Optional[bool] = None
    brightness: Optional[int] = Field(None, ge=0, le=100)
    color: Optional[Union[str, Tuple[int, int, int]]] = None


class ThermostatPayload(BaseModel):
    """Payload schema for thermostat devices."""
    mode: Optional[str] = Field(None, pattern="^(heat|cool|auto|off)$")
    target_temp: Optional[float] = None

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: Optional[str]) -> Optional[str]:
        """Validate thermostat mode is one of the allowed values."""
        if v is None:
            return v
        allowed = {"heat", "cool", "auto", "off"}
        if v not in allowed:
            raise ValueError(f"mode must be one of {allowed}, got '{v}'")
        return v


class CameraPayload(BaseModel):
    """Payload schema for camera devices."""
    power: Optional[bool] = None


# Union type for all device payloads
DevicePayload = Union[SmartPlugPayload, SmartLightPayload, ThermostatPayload, CameraPayload]

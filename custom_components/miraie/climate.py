"""The MirAIe climate platform."""

from __future__ import annotations
from typing import Any
from miraie_ac import (
    Device as MirAIeDevice,
    MirAIeHub,
    HVACMode as MHVACMode,
    FanMode,
    SwingMode,
    PresetMode,
)

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.climate import (
    PRESET_ECO,
    PRESET_BOOST,
    PRESET_NONE,
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    FAN_OFF,
    SWING_ON,
    SWING_OFF,
    PRECISION_WHOLE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:

    """Set up the MirAIe Climate Hub."""
    hub: MirAIeHub = hass.data[DOMAIN][entry.entry_id]

    entities = list(map(MirAIeClimate, hub.home.devices))

    async_add_entities(entities)


class MirAIeClimate(ClimateEntity):
    """Representation of a MirAIe Climate."""

    def __init__(self, device: MirAIeDevice) -> None:

        self._attr_hvac_modes = [
            HVACMode.AUTO,
            HVACMode.COOL,
            HVACMode.OFF,
            HVACMode.DRY,
            HVACMode.FAN_ONLY,
        ]
        self._attr_preset_modes = [PRESET_NONE, PRESET_ECO, PRESET_BOOST]
        self._attr_fan_mode = FAN_OFF
        self._attr_fan_modes = [
            FAN_AUTO,
            FAN_LOW,
            FAN_MEDIUM,
            FAN_HIGH,
            FAN_OFF,
        ]
        self._attr_swing_modes = [SWING_ON, SWING_OFF]
        self._attr_max_temp = 30.0
        self._attr_min_temp = 16.0
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.SWING_MODE
        )
        self._attr_temperature_unit = TEMP_CELSIUS
        self._attr_precision = PRECISION_WHOLE
        self._attr_unique_id = device.id
        self.device = device

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self.device.friendly_name

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        return "mdi:air-conditioner"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.device.id)
            },
            name=self.device.friendly_name,
            manufacturer=self.device.details.brand,
            model=self.device.details.model_number,
            sw_version=self.device.details.firmware_version,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.device.status.is_online

    @property
    def hvac_mode(self) -> HVACMode | str | None:

        power_mode = self.device.status.power_mode

        if power_mode.value == "off":
            return HVACMode.OFF

        mode = self.device.status.hvac_mode.value

        if mode == "fan":
            return HVACMode.FAN_ONLY

        return mode

    @property
    def current_temperature(self) -> float | None:
        return self.device.status.room_temperature

    @property
    def target_temperature(self) -> float | None:
        return self.device.status.temperature

    @property
    def preset_mode(self) -> str | None:
        return self.device.status.preset_mode.value

    @property
    def fan_mode(self) -> str | None:

        mode = self.device.status.fan_mode.value

        if mode == "quiet":
            return FAN_OFF

        return mode

    @property
    def swing_mode(self) -> str | None:

        mode = self.device.status.swing_mode.value

        if mode == 1:
            return SWING_OFF

        return SWING_ON

    def set_temperature(self, **kwargs: Any) -> None:
        self.device.set_temperature(kwargs["temperature"])

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            self.device.turn_off()
        else:

            if self.device.status.power_mode.value == "off":
                self.device.turn_on()

            if hvac_mode == HVACMode.FAN_ONLY:
                self.device.set_hvac_mode(MHVACMode("fan"))
            else:
                self.device.set_hvac_mode(MHVACMode(hvac_mode.value))

    def set_fan_mode(self, fan_mode: str) -> None:

        if fan_mode == FAN_OFF:
            self.device.set_fan_mode(FanMode("quiet"))
        else:
            self.device.set_fan_mode(FanMode(fan_mode))

    def set_swing_mode(self, swing_mode: str) -> None:

        if swing_mode == SWING_ON:
            self.device.set_swing_mode(SwingMode(0))
        else:
            self.device.set_swing_mode(SwingMode(1))

    def set_preset_mode(self, preset_mode: str) -> None:
        self.device.set_preset_mode(PresetMode(preset_mode))

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        # Sensors should also register callbacks to HA when their state changes
        self.device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self.device.remove_callback(self.async_write_ha_state)

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
    PRECISION_WHOLE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SWING_ON,
    SWING_ONE,
    SWING_TWO,
    SWING_THREE,
    SWING_FOUR,
    SWING_FIVE,
)

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
        self._attr_swing_modes = [SWING_ON, SWING_ONE, SWING_TWO, SWING_THREE, SWING_FOUR, SWING_FIVE]
        self._attr_max_temp = 30.0
        self._attr_min_temp = 16.0
        self._attr_target_temperature_step = 1
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.SWING_MODE
        )
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
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
            return SWING_ONE
        elif mode == 2:
            return SWING_TWO
        elif mode == 3:
            return SWING_THREE
        elif mode == 4:
            return SWING_FOUR
        elif mode == 5:
            return SWING_FIVE

        return SWING_ON

    async def async_set_temperature(self, **kwargs: Any) -> None:
        await self.device.set_temperature(kwargs["temperature"])

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.device.turn_off()
        else:

            if self.device.status.power_mode.value == "off":
                await self.device.turn_on()

            if hvac_mode == HVACMode.FAN_ONLY:
                await self.device.set_hvac_mode(MHVACMode("fan"))
            else:
                await self.device.set_hvac_mode(MHVACMode(hvac_mode.value))

    async def async_set_fan_mode(self, fan_mode: str) -> None:

        if fan_mode == FAN_OFF:
            await self.device.set_fan_mode(FanMode("quiet"))
        else:
            await self.device.set_fan_mode(FanMode(fan_mode))

    async def async_set_swing_mode(self, swing_mode: str) -> None:

        if swing_mode == SWING_ONE:
            await self.device.set_swing_mode(SwingMode(1))
        elif swing_mode == SWING_TWO:
            await self.device.set_swing_mode(SwingMode(2))
        elif swing_mode == SWING_THREE:
            await self.device.set_swing_mode(SwingMode(3))
        elif swing_mode == SWING_FOUR:
            await self.device.set_swing_mode(SwingMode(4))
        elif swing_mode == SWING_FIVE:
            await self.device.set_swing_mode(SwingMode(5))
        else:
            await self.device.set_swing_mode(SwingMode(0))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.device.set_preset_mode(PresetMode(preset_mode))

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        # Sensors should also register callbacks to HA when their state changes
        self.device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self.device.remove_callback(self.async_write_ha_state)

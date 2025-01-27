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
    ConvertiMode,
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
    V0,
    V1,
    V2,
    V3,
    V4,
    V5,
    H0,
    H1,
    H2,
    H3,
    H4,
    H5,
    PRESET_CONVERTI_C110,
    PRESET_CONVERTI_C100,
    PRESET_CONVERTI_C90,
    PRESET_CONVERTI_C80,
    PRESET_CONVERTI_C70,
    PRESET_CONVERTI_C55,
    PRESET_CONVERTI_C40,
    PRESET_CONVERTI_C0,
)

from .logger import LOGGER

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
        
        self._attr_should_poll: bool = False

        self._attr_hvac_modes = [
            HVACMode.AUTO,
            HVACMode.COOL,
            HVACMode.HEAT,
            HVACMode.OFF,
            HVACMode.DRY,
            HVACMode.FAN_ONLY,
        ]
        self._attr_preset_modes = [PRESET_NONE, PRESET_ECO, PRESET_BOOST, PRESET_CONVERTI_C110, PRESET_CONVERTI_C100, PRESET_CONVERTI_C90, PRESET_CONVERTI_C80, PRESET_CONVERTI_C70, PRESET_CONVERTI_C55, PRESET_CONVERTI_C40, PRESET_CONVERTI_C0]
        self._attr_fan_mode = FAN_OFF
        self._attr_fan_modes = [
            FAN_AUTO,
            FAN_LOW,
            FAN_MEDIUM,
            FAN_HIGH,
            FAN_OFF,
        ]
        self._attr_swing_modes = [V0, V1, V2, V3, V4, V5]
        self._attr_swing_horizontal_mode = [H0, H1, H2, H3, H4, H5]
        self._attr_max_temp = 30.0
        self._attr_min_temp = 16.0
        self._attr_target_temperature_step = 1
        self._enable_turn_on_off_backwards_compatibility = False
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.SWING_MODE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.SWING_HORIZONTAL_MODE
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
    def translation_key(self) -> str:
        """Return the translation key."""
        return DOMAIN

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
        if self.device.status.converti_mode in [ConvertiMode.OFF, ConvertiMode.NS]:
            return self.device.status.preset_mode.value
        return f"cv {self.device.status.converti_mode.value}"

    @property
    def fan_mode(self) -> str | None:

        mode = self.device.status.fan_mode.value

        if mode == "quiet":
            return FAN_OFF

        return mode

    @property
    def swing_mode(self) -> str | None:
        mode = self.device.status.v_swing_mode.value

        if mode == 1:
            return V1
        elif mode == 2:
            return V2
        elif mode == 3:
            return V3
        elif mode == 4:
            return V4
        elif mode == 5:
            return V5
        else:
            return V0
        
    @property
    def swing_horizontal_mode(self) -> str | None:
        mode = self.device.status.h_swing_mode.value
        
        if mode == 1:
            return H1
        elif mode == 2:
            return H2
        elif mode == 3:
            return H3
        elif mode == 4:
            return H4
        elif mode == 5:
            return H5
        else:
            return H0
    
    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.COOL)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        
        LOGGER.debug(f"Set temperature to {kwargs["temperature"]}")
        
        await self.device.set_temperature(kwargs["temperature"])

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        
        LOGGER.debug(f"Set hvac mode to {hvac_mode}")
        
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
        
        LOGGER.debug(f"Set fan mode to {fan_mode}")
        
        if fan_mode == FAN_OFF:
            await self.device.set_fan_mode(FanMode("quiet"))
        else:
            await self.device.set_fan_mode(FanMode(fan_mode))

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        
        LOGGER.debug(f"Set swing mode to {swing_mode}")
        
        if swing_mode.startswith('V'):
            if swing_mode == V1:
                await self.device.set_v_swing_mode(SwingMode(1))
            elif swing_mode == V2:
                await self.device.set_v_swing_mode(SwingMode(2))
            elif swing_mode == V3:
                await self.device.set_v_swing_mode(SwingMode(3))
            elif swing_mode == V4:
                await self.device.set_v_swing_mode(SwingMode(4))
            elif swing_mode == V5:
                await self.device.set_v_swing_mode(SwingMode(5))
            else:
                await self.device.set_v_swing_mode(SwingMode(0))
                
        elif swing_mode.startswith('H'):
            if swing_mode == H1:
                await self.device.set_h_swing_mode(SwingMode(1))
            elif swing_mode == H2:
                await self.device.set_h_swing_mode(SwingMode(2))
            elif swing_mode == H3:
                await self.device.set_h_swing_mode(SwingMode(3))
            elif swing_mode == H4:
                await self.device.set_h_swing_mode(SwingMode(4))
            elif swing_mode == H5:
                await self.device.set_h_swing_mode(SwingMode(5))
            else:
                await self.device.set_h_swing_mode(SwingMode(0))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        
        LOGGER.debug(f"Set preset mode to {preset_mode}")
        
        if preset_mode.startswith("cv"):
            preset_mode = int(preset_mode.split(" ")[1])
            await self.device.set_converti_mode(ConvertiMode(preset_mode))
        else:
            await self.device.set_preset_mode(PresetMode(preset_mode))

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        
        LOGGER.debug("Successfully added to HA")
        
        # Sensors should also register callbacks to HA when their state changes
        self.device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        
        LOGGER.debug("Successfully removed from HA")
        
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self.device.remove_callback(self.async_write_ha_state)

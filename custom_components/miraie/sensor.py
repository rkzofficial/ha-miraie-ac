from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta

import aiohttp
from miraie_ac import Device as MirAIeDevice, MirAIeHub, ConsumptionPeriodType

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN
from .logger import LOGGER
from .utils import get_last_sunday


class MirAIeTimerSensor(SensorEntity):
    """Timestamp sensor for an AC's scheduled on-timer or off-timer.

    The state is the absolute UTC datetime when the AC will fire the
    timer, or `None` (unavailable) if no timer is set.
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_should_poll = False

    def __init__(self, device: MirAIeDevice, kind: str):
        if kind not in ("off", "on"):
            raise ValueError(kind)
        self.device = device
        self.kind = kind
        self._attr_unique_id = f"{device.id}_{kind}_timer_at"
        self._attr_name = f"{device.friendly_name} {kind.capitalize()} timer"
        self._attr_translation_key = f"{kind}_timer"

    @property
    def icon(self) -> str:
        return "mdi:timer-off-outline" if self.kind == "off" else "mdi:timer-play-outline"

    @property
    def native_value(self) -> datetime | None:
        epoch = self.device.status.off_timer_at if self.kind == "off" else self.device.status.on_timer_at
        if epoch is None or epoch <= 0:
            return None
        return datetime.fromtimestamp(epoch, tz=timezone.utc)

    @property
    def available(self) -> bool:
        return self.device.status.is_online

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.id)},
            name=self.device.friendly_name,
            manufacturer=self.device.details.brand,
            model=self.device.details.model_number,
            sw_version=self.device.details.firmware_version,
        )

    async def async_added_to_hass(self) -> None:
        self.device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        self.device.remove_callback(self.async_write_ha_state)


CUTOFF_HOUR = 12

class MirAIeEnergySensor(SensorEntity, ABC):
    """Sensor for AC Power Consumption."""
    @property
    @abstractmethod
    def period_type(self) -> ConsumptionPeriodType:
        return None

    def __init__(self, hub: MirAIeHub, device: MirAIeDevice):
        """Initialize the sensor."""
        self.hub = hub
        self.device = device
        self._attr_name = f"{device.name} {self.period_type.value} Energy"
        self._attr_unique_id = f"sensor.{device.name.lower()}_{device.id}_{self.period_type.value.lower()}_energy"
        self._attr_should_poll = False
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_suggested_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_suggested_display_precision = 2
        self._attr_native_value = None

    async def async_update(self):
        """Update the sensor state with the latest energy consumption data."""
        now = datetime.now().astimezone()
        cutoff_time = now.replace(hour=CUTOFF_HOUR, minute=0, second=0, microsecond=0)
        if not self.hub.http or self.hub.http.closed:
            self.hub.http = aiohttp.ClientSession()
        consumption = await self.get_energy_consumption()

        """Consumption figures are updated on the server some time between 7-10 am the next day.
        This skips setting the state to unavailable if the value is None and it's not yet
        past the cutoff time.
        """
        if consumption is None and now <= cutoff_time:
            """Skip update if no new data and it's before the cutoff time."""
            return

        await self._set_last_reset_time()
        self._attr_native_value = consumption

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        LOGGER.debug(f"Removing energy consumption entity ({self._attr_name}) from HA")
        if self.hub.http and not self.hub.http.closed:
            await self.hub.http.close()
        return await super().async_will_remove_from_hass()

    @abstractmethod
    async def get_energy_consumption(self) -> float | None:
        """Fetch the latest power consumption data."""
        raise NotImplementedError

    @abstractmethod
    async def _set_last_reset_time(self):
        """Set the last reset time for the sensor entity."""
        raise NotImplementedError

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

class MirAIeDailyEnergySensor(MirAIeEnergySensor):
    @property
    def period_type(self) -> ConsumptionPeriodType:
        return ConsumptionPeriodType.DAILY

    async def get_energy_consumption(self) -> float | None:
        """Fetch the latest daily energy consumption data."""
        yesterday = datetime.today().date() - timedelta(days=1)
        date_string = yesterday.strftime("%d%m%Y")
        LOGGER.debug(f"Fetching {self.period_type.value} energy consumption for device: {self._attr_name}, period: {date_string}")
        consumption = await self.hub.get_energy_consumption(self.device, self.period_type, from_date=date_string)
        return consumption.get(date_string)

    async def _set_last_reset_time(self):
        """Set the last reset time for the daily energy sensor entity."""
        now = datetime.now(timezone.utc).astimezone()
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if not getattr(self, "_attr_last_reset", None) or self._attr_last_reset < start_of_today:
            self._attr_last_reset = now

class MirAIeWeeklyEnergySensor(MirAIeEnergySensor):
    @property
    def period_type(self) -> ConsumptionPeriodType:
        return ConsumptionPeriodType.WEEKLY

    async def get_energy_consumption(self) -> float | None:
        """Fetch the latest weekly energy consumption data."""
        date_string = get_last_sunday().strftime("%d%m%Y")
        LOGGER.debug(f"Fetching {self.period_type.value} energy consumption for device: {self._attr_name}, period: {date_string}")
        consumption = await self.hub.get_energy_consumption(self.device, self.period_type, from_date=date_string)
        return consumption.get(date_string)

    async def _set_last_reset_time(self):
        """Set the last reset time for the weekly energy sensor entity."""
        now = datetime.now(timezone.utc).astimezone()
        start_of_week = (now - timedelta(days=now.weekday() + 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        if not getattr(self, "_attr_last_reset", None) or self._attr_last_reset < start_of_week:
            self._attr_last_reset = now

class MirAIeMonthlyEnergySensor(MirAIeEnergySensor):
    @property
    def period_type(self) -> ConsumptionPeriodType:
        return ConsumptionPeriodType.MONTHLY

    async def get_energy_consumption(self) -> float | None:
        """Fetch the latest monthly energy consumption data."""
        yesterday = datetime.today().date() - timedelta(days=1)
        date_string = yesterday.strftime("%m%Y")
        LOGGER.debug(f"Fetching {self.period_type.value} energy consumption for device: {self._attr_name}, period: {date_string}")
        consumption = await self.hub.get_energy_consumption(self.device, self.period_type, from_date=date_string)
        return consumption.get(date_string)

    async def _set_last_reset_time(self):
        """Set the last reset time for the monthly energy sensor entity."""
        now = datetime.now(timezone.utc).astimezone()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if not getattr(self, "_attr_last_reset", None) or self._attr_last_reset < start_of_month:
            self._attr_last_reset = now


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up MirAIe energy sensors from a config entry."""
    hub: MirAIeHub = hass.data[DOMAIN][entry.entry_id]
    energy_sensors: list[MirAIeEnergySensor] = []
    timer_sensors: list[MirAIeTimerSensor] = []
    for device in hub.home.devices:
        energy_sensors += [
            MirAIeDailyEnergySensor(hub, device),
            MirAIeWeeklyEnergySensor(hub, device),
            MirAIeMonthlyEnergySensor(hub, device),
        ]
        timer_sensors += [
            MirAIeTimerSensor(device, "off"),
            MirAIeTimerSensor(device, "on"),
        ]
    async_add_entities(energy_sensors, update_before_add=True)
    async_add_entities(timer_sensors)

    async def update_sensors(now=None):
        for sensor in energy_sensors:
            await sensor.async_update()
            sensor.async_write_ha_state()  # Ensure HA is notified of new data

    async_track_time_interval(hass, update_sensors, timedelta(minutes=30))

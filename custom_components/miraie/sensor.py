from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta

import aiohttp
from miraie_ac import Device as MirAIeDevice, MirAIeHub, ConsumptionPeriodType

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN
from .logger import LOGGER
from .utils import get_last_sunday


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
    sensors = []
    for device in hub.home.devices:
        sensors += [
            MirAIeDailyEnergySensor(hub, device),
            MirAIeWeeklyEnergySensor(hub, device),
            MirAIeMonthlyEnergySensor(hub, device),
        ]
    async_add_entities(sensors, update_before_add=True)  # Register sensors

    async def update_sensors(now=None):
        for sensor in sensors:
            await sensor.async_update()
            sensor.async_write_ha_state()  # Ensure HA is notified of new data

    async_track_time_interval(hass, update_sensors, timedelta(minutes=30))

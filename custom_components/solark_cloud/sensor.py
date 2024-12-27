"""Sol-Ark Cloud integration sensors."""

from dataclasses import dataclass
import logging
import time
import typing

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SolArkCloudCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SolArkCloudSensorEntityDescription(SensorEntityDescription):
    """Sensor entity description for SolarEdge."""

    only_if_key: str | None = None
    source_key: str | None = None
    accum_key: str | None = None

    # min_power: int = 0
    # pv_to: bool = False
    # to_load: bool = False
    # to_grid: bool = False
    # to_battery: bool = False
    # battery_to: bool = False
    # grid_to: bool = False
    # generator_to: bool = False
    # min_to: bool = False
    # exists_generator: bool = False
    # exists_min: bool = False
    # generator_on: bool = False
    # micro_on: bool = False
    # exists_meter: bool = False
    # bms_comm_fault_flag: bool = False
    # exist_think_power: bool = False


SENSOR_TYPES = [
    SolArkCloudSensorEntityDescription(
        key="soc",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement="%",
    ),
    SolArkCloudSensorEntityDescription(
        key="battery_power_drain",
        source_key="battery_power",
        only_if_key="battery_to",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
    ),
    SolArkCloudSensorEntityDescription(
        key="battery_power_drain_accum",
        accum_key="battery_power",
        only_if_key="battery_to",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement="Wh",
    ),
    SolArkCloudSensorEntityDescription(
        key="battery_power_charge",
        source_key="battery_power",
        only_if_key="to_battery",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
    ),
    SolArkCloudSensorEntityDescription(
        key="battery_power_charge_accum",
        accum_key="battery_power",
        only_if_key="to_battery",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement="Wh",
    ),
    SolArkCloudSensorEntityDescription(
        key="grid_or_meter_power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
    ),
    SolArkCloudSensorEntityDescription(
        key="grid_or_meter_power_accum",
        accum_key="grid_or_meter_power",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement="Wh",
    ),
    SolArkCloudSensorEntityDescription(
        key="load_or_eps_power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
    ),
    SolArkCloudSensorEntityDescription(
        key="load_or_eps_power_accum",
        accum_key="load_or_eps_power",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement="Wh",
    ),
    SolArkCloudSensorEntityDescription(
        key="pv_power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
    ),
    SolArkCloudSensorEntityDescription(
        key="pv_power_accum",
        accum_key="pv_power",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement="Wh",
    ),
    SolArkCloudSensorEntityDescription(
        key="generator_power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
    ),
    SolArkCloudSensorEntityDescription(
        key="generator_power_accum",
        accum_key="generator_power",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement="Wh",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sensors."""
    # This gets the data update coordinator from hass.data as specified in your __init__.py
    coordinator: SolArkCloudCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ].coordinator

    # Enumerate all the sensors in your data value from your DataUpdateCoordinator and add an instance of your sensor class
    # to a list for each one.
    # This maybe different in your specific case, depending on how your data is structured
    sensors = []
    for plant in coordinator.data["plants"].values():
        sensors.extend(
            [
                PlantSensor(
                    coordinator,
                    plant,
                    coordinator.data["flows"].get(plant["id"]),
                    sensor,
                )
                for sensor in SENSOR_TYPES
            ]
        )

    # Create the sensors.
    async_add_entities(sensors)


class PlantSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a sensor."""

    def __init__(
        self,
        coordinator: SolArkCloudCoordinator,
        plant: dict,
        flow: dict,
        sensor: SolArkCloudSensorEntityDescription,
    ) -> None:
        """Initialise sensor."""
        super().__init__(coordinator)
        self.plant = plant
        self.flow = flow
        self.sensor = sensor
        self.accumulated = 0
        self.last_updated = time.time()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        # This method is called by your DataUpdateCoordinator when a successful update runs.
        self.flow = self.coordinator.data["flows"][self.plant["id"]]

        # Handle accumulation if we're an accumulator. Note, we have all the data for the flows
        # here (aka, all sensors.)
        now = time.time()
        if self.sensor.accum_key and (
            (not self.sensor.only_if_key) or getattr(self.flow, self.sensor.only_if_key)
        ):
            self.accumulated += (getattr(self.flow, self.sensor.accum_key) / 3600) * (
                now - self.last_updated
            )
        self.last_updated = now

        self.async_write_ha_state()

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return device class."""
        # https://developers.home-assistant.io/docs/core/entity/sensor/#available-device-classes
        return self.sensor.device_class

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        # Identifiers are what group entities into the same device.
        # If your device is created elsewhere, you can just specify the identifiers parameter.
        # If your device connects via another device, add via_device parameter with the identifiers of that device.
        return DeviceInfo(
            name=f"Sol-Ark Cloud Plant #{self.plant['id']}",
            identifiers={
                (
                    DOMAIN,
                    self.plant["id"],
                )
            },
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"Sol-Ark Cloud Plant #{self.plant['id']} {self.sensor.key}"

    @property
    def native_value(self) -> int | float:
        """Return the state of the entity."""
        # Using native value and native unit of measurement, allows you to change units
        # in Lovelace and HA will automatically calculate the correct value.

        # If we're an accumulator, return this as our value.
        if self.sensor.accum_key:
            return self.accumulated

        # Only emit if this key is true, if it exists.
        if self.sensor.only_if_key and not getattr(self.flow, self.sensor.only_if_key):
            return 0

        # If we have a source key, use that, otherwise use the regular key.
        if self.sensor.source_key:
            return getattr(self.flow, self.sensor.source_key)
        return getattr(self.flow, self.sensor.key)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of temperature."""
        return self.sensor.native_unit_of_measurement

    @property
    def state_class(self) -> str | None:
        """Return state class."""
        # https://developers.home-assistant.io/docs/core/entity/sensor/#available-state-classes
        return self.sensor.state_class

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        # All entities must have a unique id.  Think carefully what you want this to be as
        # changing it later will cause HA to create new entities.
        return f"{DOMAIN}-{self.plant['id']}-{self.sensor.key}"

    @property
    def extra_state_attributes(self) -> dict[str, typing.Any]:
        """Return the extra state attributes."""
        # Add any additional attributes you want on your sensor.
        # attrs = {}
        # attrs["extra_info"] = "Extra Info"
        return {}

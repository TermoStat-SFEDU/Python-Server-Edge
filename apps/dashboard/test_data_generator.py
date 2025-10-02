# File: apps/dashboard/test_data_generator.py
import logging
import random
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Tuple, Type

from django.db import transaction
from django.utils import timezone

from apps.auditing.models import Event, LogEntry
from apps.sensor.models import Device, TemperatureReading

logger = logging.getLogger(__name__)


class TempScenario(Enum):
    """Enumeration for different temperature measurement scenarios."""
    NORMAL = (36.4, 37.2)
    FEVER = (37.5, 39.0)
    LOW_TEMP = (35.0, 36.2)


@dataclass
class SimulatedDeviceState:
    """Represents the in-memory state of a simulated device."""
    model: Device
    status: str = 'active'
    is_broken: bool = False
    inactive_until: datetime = field(default_factory=timezone.now)


class TestDataGenerator:
    """
    A singleton class to generate and write simulated sensor data to the database.

    This class simulates various realistic scenarios, including different body
    temperatures, sensor inaccuracies, device disconnections, new device
    additions, and DoS attacks.
    """
    _instance: "Optional[TestDataGenerator]" = None
    _lock = threading.Lock()

    def __new__(cls: Type["TestDataGenerator"]) -> "TestDataGenerator":
        """
        Implement the singleton pattern for the TestDataGenerator.

        Args:
            cls: The class being instantiated.

        Returns:
            The single instance of the TestDataGenerator class.
        """
        if cls._instance is None:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(TestDataGenerator, cls).__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """
        Initialize the TestDataGenerator instance.

        Sets up the initial state, including the in-memory device state cache
        and a reference to the 'DOS_DETECTED' event type for simulations.
        """
        self.devices_state: Dict[str, SimulatedDeviceState] = {}
        try:
            self.dos_event: Optional[Event] = Event.objects.get(identifier='DOS_DETECTED')
        except Event.DoesNotExist:
            logger.error("DOS_DETECTED event type not found. DoS simulation will fail.")
            self.dos_event = None

    def _create_device_in_db(self, ip: str, timestamp: datetime, is_broken: bool = False) -> None:
        """
        Create a new Device instance in the database and in the local state.

        Args:
            ip: The IP address for the new simulated device.
            timestamp: The creation timestamp for the device.
            is_broken: A boolean flag indicating if the device should simulate
                faulty behavior (e.g., sending data too frequently).
        """
        device_model, created = Device.objects.get_or_create(
            ip_address=ip,
            defaults={'created_at': timestamp, 'last_seen': timestamp}
        )
        if created:
            self.devices_state[ip] = SimulatedDeviceState(model=device_model, is_broken=is_broken)
            logger.info(f"Simulated new device created in DB: {ip} (Broken: {is_broken})")

    @transaction.atomic
    def generate_initial_data(self) -> None:
        """
        Clear old data and generate a historical dataset in the database.

        This method is intended to be called by a management command to seed
        the database. It wipes existing test data, creates a random number of
        simulated devices, and populates `TemperatureReading` records for the
        last 24 hours to create a realistic-looking history.
        """
        with self._lock:
            logger.info("Clearing old test data from database...")
            TemperatureReading.objects.all().delete()
            LogEntry.objects.all().delete()
            Device.objects.all().delete()
            self.devices_state.clear()

            now = timezone.now()
            num_devices = random.randint(5, 8)
            broken_indices = random.sample(range(num_devices), k=random.randint(1, 2))
            
            for i in range(num_devices):
                ip = f"192.168.1.{100 + i}"
                self._create_device_in_db(ip, now, is_broken=(i in broken_indices))

            readings_to_create: List[TemperatureReading] = []
            for state in self.devices_state.values():
                # Generate readings every 10 minutes for the last 24 hours
                for i in range(24 * 6):  
                    timestamp = now - timedelta(minutes=i * 10)
                    
                    # Broken devices send more data, even historically
                    num_readings = random.randint(2, 4) if state.is_broken else 1
                    for j in range(num_readings):
                        ts = timestamp - timedelta(seconds=j * 15)
                        contact_temp, non_contact_temp = self._get_reading_pair()
                        readings_to_create.append(
                            TemperatureReading(
                                device=state.model,
                                timestamp=ts,
                                contact_temp=contact_temp,
                                non_contact_temp=non_contact_temp,
                            )
                        )
            
            logger.info(f"Bulk creating {len(readings_to_create)} historical readings...")
            TemperatureReading.objects.bulk_create(readings_to_create)
            
            Device.objects.update(last_seen=now)
            logger.info("Updated 'last_seen' for all simulated devices.")

    def _get_reading_pair(self) -> Tuple[float, float]:
        """
        Generate a realistic pair of contact and non-contact temperatures.

        This method simulates different health scenarios (normal, fever, low temp)
        and adds random noise to generate plausible readings for both contact
        and non-contact sensors on a device.

        Returns:
            A tuple containing the simulated contact and non-contact temperatures.
        """
        scenario = random.choices(
            list(TempScenario), weights=[85, 10, 5], k=1
        )[0]
        
        min_temp, max_temp = scenario.value
        true_temp = random.uniform(min_temp, max_temp)
        
        contact_noise = random.uniform(-0.2, 0.2)
        contact_temp = round(true_temp + contact_noise, 2)
        
        non_contact_offset = -0.3
        non_contact_noise = random.uniform(-0.8, 0.8)
        non_contact_temp = round(true_temp + non_contact_offset + non_contact_noise, 2)
        
        return contact_temp, non_contact_temp

    def tick(self) -> None:
        """
        Advance the simulation by one step and write new data to the database.

        This method is designed to be called periodically by a scheduler. On each
        tick, it simulates various events such as new device registration, DoS
        attacks, devices going offline/online, and generation of new temperature
        readings. The new data is then written to the database.
        """
        with self._lock:
            now = timezone.now()
            active_devices_to_update: List[Device] = []

            if random.random() < 0.01 and len(self.devices_state) < 15:
                new_ip = f"192.168.1.{100 + len(self.devices_state)}"
                self._create_device_in_db(new_ip, now)

            if self.dos_event and random.random() < 0.02 and self.devices_state:
                victim_ip = random.choice(list(self.devices_state.keys()))
                device_model = self.devices_state[victim_ip].model
                LogEntry.objects.create(
                    event=self.dos_event,
                    device=device_model,
                    details={"ip_address": victim_ip, "simulated": True}
                )

            new_readings: List[TemperatureReading] = []
            for state in self.devices_state.values():
                if state.status == 'inactive' and now > state.inactive_until:
                    state.status = 'active'
                    logger.info(f"Device {state.model.ip_address} is back online.")
                
                if state.status == 'active' and random.random() < 0.03:
                    inactive_duration = timedelta(minutes=random.randint(2, 15))
                    state.inactive_until = now + inactive_duration
                    state.status = 'inactive'
                    logger.info(f"Device {state.model.ip_address} went offline for {inactive_duration}.")
                
                if state.status == 'active':
                    num_readings = random.randint(2, 4) if state.is_broken else 1
                    for i in range(num_readings):
                        ts = now - timedelta(seconds=i * 1) # Rapid fire for broken devices
                        contact_temp, non_contact_temp = self._get_reading_pair()
                        new_readings.append(
                            TemperatureReading(
                                device=state.model,
                                timestamp=ts,
                                contact_temp=contact_temp,
                                non_contact_temp=non_contact_temp,
                            )
                        )
                    active_devices_to_update.append(state.model)

            if new_readings:
                with transaction.atomic():
                    TemperatureReading.objects.bulk_create(new_readings)
                    device_ids = [d.id for d in active_devices_to_update]
                    Device.objects.filter(id__in=device_ids).update(last_seen=now)

generator = TestDataGenerator()

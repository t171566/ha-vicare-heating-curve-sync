
"""Bidirectional synchronization between ViCare and input_number helpers."""

from __future__ import annotations

import asyncio
import logging
import math

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import CIRCUIT_HELPERS

_LOGGER = logging.getLogger(__name__)

RETRY_DELAY = 60
VALUE_TOLERANCE = 0.0001


def _get_supported_circuits(api):
    """Load and validate the first two ViCare heating circuits."""
    
    
    try:
        circuits = api.circuits

        if circuits is None or len(circuits) < 2:
            return None

        for circuit in circuits[:2]:
            slope = float(circuit.getHeatingCurveSlope())
            shift = float(circuit.getHeatingCurveShift())

            if not math.isfinite(slope) or not math.isfinite(shift):
                return None

        return circuits

    except Exception:
        return None


class ViCareCurveSync:
    """Synchronize ViCare heating circuits with HA input_number helpers."""

    def __init__(
        self,
        hass: HomeAssistant,
        vicare_entry_id: str,
        selected_device_id: str,
    ) -> None:
   
        """Initialize the synchronizer."""
        self.hass = hass
        self.vicare_entry_id = vicare_entry_id
        self.selected_device_id = selected_device_id

        self.device = None
        self.circuits = None

        self._remove_state_listener = None
        self._remove_coordinator_listener = None
        self._coordinator = None
        self._lock = asyncio.Lock()
        self._stopped = False
        self._retry_task = None
        self._last_error = {}
        self._pending_writes = {}


    async def _async_refresh_vicare_references(self) -> bool:
        """Resolve current ViCare device, circuits and coordinator."""
        if self._stopped:
            return False

        vicare_entry = self.hass.config_entries.async_get_entry(
            self.vicare_entry_id
        )

        if (
            vicare_entry is None
            or vicare_entry.domain != "vicare"
            or vicare_entry.state is not ConfigEntryState.LOADED
        ):
            return False

        vicare_data = getattr(vicare_entry, "runtime_data", None)

        if vicare_data is None:
            return False

        devices = getattr(vicare_data, "devices", [])

        for index, device in enumerate(devices):
            device_id = device.serial or str(index)

            if device_id != self.selected_device_id:
                continue

            api = getattr(device, "api", None)

            if api is None:
                return False

            circuits = await self.hass.async_add_executor_job(
                _get_supported_circuits,
                api,
            )

            if circuits is None:
                return False

            coordinator = getattr(device, "coordinator", None)

            if (
                coordinator is None
                or not getattr(coordinator, "last_update_success", False)
            ):
                return False

            if coordinator is not self._coordinator:
                if self._remove_coordinator_listener is not None:
                    self._remove_coordinator_listener()
                    self._remove_coordinator_listener = None

                self._coordinator = coordinator
                self._remove_coordinator_listener = (
                    coordinator.async_add_listener(
                        self._handle_coordinator_update
                    )
                )

            self.device = device
            self.circuits = circuits
            return True

        return False
        
    async def async_start(self) -> None:
        """Start listeners and perform initial synchronization."""
        entities = [
            entity_id
            for mapping in CIRCUIT_HELPERS.values()
            for entity_id in (mapping["slope"], mapping["shift"])
        ]

        self._remove_state_listener = async_track_state_change_event(
            self.hass,
            entities,
            self._async_state_changed,
        )

        if not await self._async_refresh_vicare_references():
            _LOGGER.warning(
                "ViCare is not ready yet; synchronization will be retried"
            )
            self._schedule_retry()
            return

        await self.async_update_helpers_from_vicare()    
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresh helpers and retry pending writes after ViCare updates."""
        if self._stopped:
            return

        self.hass.async_create_task(
            self._async_handle_coordinator_update()
        )

    async def _async_handle_coordinator_update(self) -> None:
        """Process a ViCare update and retry pending writes."""
        await self.async_update_helpers_from_vicare()

        if self._stopped:
            return

        for circuit_index, pending_values in list(
            self._pending_writes.items()
        ):
            for changed_value, value in list(
                pending_values.items()
            ):
                await self._async_write_curve(
                    circuit_index,
                    changed_value,
                    value,
                )

    async def async_stop(self) -> None:
        """Remove listeners and stop pending retries."""
        self._stopped = True

        if self._retry_task is not None:
            self._retry_task.cancel()
            self._retry_task = None

        if self._remove_state_listener is not None:
            self._remove_state_listener()
            self._remove_state_listener = None

        if self._remove_coordinator_listener is not None:
            self._remove_coordinator_listener()
            self._remove_coordinator_listener = None 

    async def _read_curve(
        self, circuit_index: int
    ) -> tuple[float, float]:
        """Read slope and shift from ViCare."""
        if self.circuits is None:
            raise RuntimeError("ViCare heating circuits are not available")

        circuit = self.circuits[circuit_index]

        return await self.hass.async_add_executor_job(
            lambda: (
                float(circuit.getHeatingCurveSlope()),
                float(circuit.getHeatingCurveShift()),
            )
        )
        
    def _schedule_retry(self) -> None:
        """Schedule retries until ViCare synchronization recovers."""
        if self._stopped:
            return

        if self._retry_task is not None and not self._retry_task.done():
            return

        async def retry() -> None:
            try:
                while not self._stopped:
                    await asyncio.sleep(RETRY_DELAY)

                    if self._stopped:
                        return

                    _LOGGER.info("Retrying ViCare synchronization")

                    await self.async_update_helpers_from_vicare()

                    for circuit_index, pending_values in list(
                        self._pending_writes.items()
                    ):
                        for changed_value, value in list(
                            pending_values.items()
                        ):
                            await self._async_write_curve(
                                circuit_index,
                                changed_value,
                                value,
                            )

                    if not self._last_error and not self._pending_writes:
                        return

            except asyncio.CancelledError:
                raise
            finally:
                self._retry_task = None

        self._retry_task = self.hass.async_create_task(retry())
        
    async def async_update_helpers_from_vicare(self) -> None:
        """Copy current ViCare values into the HA helpers."""
        if self._stopped:
            return
        if not await self._async_refresh_vicare_references():
            self._last_error[-1] = "ViCare is not ready"
            self._schedule_retry()
            return

        self._last_error.pop(-1, None)

        had_error = False

        async with self._lock:
            for circuit_index, mapping in CIRCUIT_HELPERS.items():
                try:
                    slope, shift = await self._read_curve(circuit_index)

                    if not math.isfinite(slope) or not math.isfinite(shift):
                        raise ValueError("ViCare returned an invalid curve value")

                    pending = self._pending_writes.get(circuit_index, {})

                    if "slope" not in pending:
                        await self._set_helper_if_changed(
                            mapping["slope"], slope
                        )

                    if "shift" not in pending:
                        await self._set_helper_if_changed(
                            mapping["shift"], shift
                        )
                        
                    if not self._pending_writes.get(circuit_index):
                        self._last_error.pop(circuit_index, None)

                except Exception as err:
                    had_error = True
                    self._last_error[circuit_index] = str(err)
                    _LOGGER.warning(
                        "Could not read ViCare heating curve for %s "
                        "(circuit %s): %s",
                        mapping["name"],
                        circuit_index,
                        err,
                    )

        if had_error:
            self._schedule_retry()

    
    async def _set_helper_if_changed(
        self, entity_id: str, value: float
    ) -> None:
        """Update a helper only when its value differs."""
        state = self.hass.states.get(entity_id)

        if state is None:
            raise ValueError(
                f"Configured helper {entity_id} does not exist"
            )

        try:
            current = float(state.state)
        except (TypeError, ValueError):
            current = None

        if current is not None and abs(current - value) < VALUE_TOLERANCE:
            return

        attributes = state.attributes

        try:
            minimum = float(attributes.get("min", float("-inf")))
            maximum = float(attributes.get("max", float("inf")))
        except (TypeError, ValueError):
            minimum = float("-inf")
            maximum = float("inf")

        if (
            not math.isfinite(value)
            or not minimum <= value <= maximum
        ):
            raise ValueError(
                f"ViCare value {value} for {entity_id} is outside "
                f"helper range {minimum} to {maximum}"
            )

        await self.hass.services.async_call(
            "input_number",
            "set_value",
            {
                "entity_id": entity_id,
                "value": value,
            },
            blocking=True,
        )

    def _clear_pending_write(
        self, circuit_index: int, changed_value: str
    ) -> None:
        """Clear one pending value without removing other pending values."""
        pending = self._pending_writes.get(circuit_index)

        if pending is None:
            return

        pending.pop(changed_value, None)

        if not pending:
            self._pending_writes.pop(circuit_index, None)
    
    @callback
    def _async_state_changed(self, event: Event) -> None:
        """Handle manual changes of HA input_number helpers."""
        if self._stopped:
            return

        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")

        if new_state is None:
            return

        try:
            value = float(new_state.state)
        except (TypeError, ValueError):
            return

        if not math.isfinite(value):
            _LOGGER.warning(
                "Ignoring invalid helper value for %s",
                entity_id,
            )
            return

        for circuit_index, mapping in CIRCUIT_HELPERS.items():
            if entity_id == mapping["slope"]:
                self.hass.async_create_task(
                    self._async_write_curve(
                        circuit_index, "slope", value
                    )
                )
                return

            if entity_id == mapping["shift"]:
                self.hass.async_create_task(
                    self._async_write_curve(
                        circuit_index, "shift", value
                    )
                )
                return

    async def _async_write_curve(
        self,
        circuit_index: int,
        changed_value: str,
        value: float,
    ) -> None:
        """Write a changed helper value to ViCare."""
        if self._stopped:
            return

        mapping = CIRCUIT_HELPERS[circuit_index]

        async with self._lock:
            if self._stopped:
                return

            if not await self._async_refresh_vicare_references():
                self._pending_writes.setdefault(circuit_index, {})[
                    changed_value
                ] = value
                self._last_error[circuit_index] = "ViCare is not ready"
                self._schedule_retry()
                return

            circuit = self.circuits[circuit_index]

            try:
                slope, shift = await self._read_curve(circuit_index)

                if not math.isfinite(slope) or not math.isfinite(shift):
                    raise ValueError(
                        "ViCare returned an invalid curve value"
                    )

                if changed_value == "slope":
                    if abs(slope - value) < VALUE_TOLERANCE:
                        self._clear_pending_write(circuit_index, changed_value)
                        if not self._pending_writes.get(circuit_index):
                            self._last_error.pop(circuit_index, None)
                        return

                    minimum, maximum = await self.hass.async_add_executor_job(
                        lambda: (
                            float(circuit.getHeatingCurveSlopeMin()),
                            float(circuit.getHeatingCurveSlopeMax()),
                        )
                    )

                    if (
                        not math.isfinite(value)
                        or not math.isfinite(minimum)
                        or not math.isfinite(maximum)
                        or minimum > maximum
                        or not minimum <= value <= maximum
                    ):
                        self._clear_pending_write(circuit_index, changed_value)
                        if not self._pending_writes.get(circuit_index):
                            self._last_error.pop(circuit_index, None)
                        _LOGGER.warning(
                            "Slope %s for %s is outside ViCare limits %s to %s",
                            value,
                            mapping["name"],
                            minimum,
                            maximum,
                        )
                        return

                    slope = value

                else:
                    if abs(shift - value) < VALUE_TOLERANCE:
                        self._clear_pending_write(circuit_index, changed_value)
                        if not self._pending_writes.get(circuit_index):
                            self._last_error.pop(circuit_index, None)
                        return

                    minimum, maximum = await self.hass.async_add_executor_job(
                        lambda: (
                            float(circuit.getHeatingCurveShiftMin()),
                            float(circuit.getHeatingCurveShiftMax()),
                        )
                    )

                    if (
                        not math.isfinite(value)
                        or not math.isfinite(minimum)
                        or not math.isfinite(maximum)
                        or minimum > maximum
                        or not minimum <= value <= maximum
                    ):
                        self._clear_pending_write(circuit_index, changed_value)
                        if not self._pending_writes.get(circuit_index):
                            self._last_error.pop(circuit_index, None)
                        _LOGGER.warning(
                            "Shift %s for %s is outside ViCare limits %s to %s",
                            value,
                            mapping["name"],
                            minimum,
                            maximum,
                        )
                        return

                    shift = value

                await self.hass.async_add_executor_job(
                    circuit.setHeatingCurve,
                    shift,
                    slope,
                )

                self._clear_pending_write(circuit_index, changed_value)
                if not self._pending_writes.get(circuit_index):
                    self._last_error.pop(circuit_index, None)

                _LOGGER.info(
                    "Updated ViCare %s: slope=%s, shift=%s",
                    mapping["name"],
                    slope,
                    shift,
                )

            except Exception as err:
                self._last_error[circuit_index] = str(err)
                self._pending_writes.setdefault(circuit_index, {})[
                    changed_value
                ] = value
                _LOGGER.warning(
                    "Could not write heating curve to ViCare for %s: %s",
                    mapping["name"],
                    err,
                )
                self._schedule_retry()


"""Bidirectional synchronization between ViCare and input_number helpers."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import CIRCUIT_HELPERS

_LOGGER = logging.getLogger(__name__)


class ViCareCurveSync:
    """Synchronize ViCare heating circuits with HA input_number helpers."""

    def __init__(self, hass: HomeAssistant, vicare_device, circuits) -> None:
        """Initialize the synchronizer."""
        self.hass = hass
        self.device = vicare_device
        self.circuits = circuits

        self._remove_state_listener = None
        self._remove_coordinator_listener = None
        self._lock = asyncio.Lock()
        self._stopped = False

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

        coordinator = self.device.coordinator
        if coordinator is not None:
            self._remove_coordinator_listener = (
                coordinator.async_add_listener(
                    self._handle_coordinator_update
                )
            )

        await self.async_update_helpers_from_vicare()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresh helpers after the official ViCare integration updates."""
        if not self._stopped:
            self.hass.async_create_task(
                self.async_update_helpers_from_vicare()
            )

    async def async_stop(self) -> None:
        """Remove listeners."""
        self._stopped = True

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
        circuit = self.circuits[circuit_index]

        return await self.hass.async_add_executor_job(
            lambda: (
                float(circuit.getHeatingCurveSlope()),
                float(circuit.getHeatingCurveShift()),
            )
        )

    async def async_update_helpers_from_vicare(self) -> None:
        """Copy current ViCare values into the HA helpers."""
        if self._stopped:
            return

        async with self._lock:
            for circuit_index, mapping in CIRCUIT_HELPERS.items():
                try:
                    slope, shift = await self._read_curve(circuit_index)
                except Exception:
                    _LOGGER.exception(
                        "Could not read ViCare heating curve for circuit %s",
                        circuit_index,
                    )
                    continue

                await self._set_helper_if_changed(
                    mapping["slope"], slope
                )
                await self._set_helper_if_changed(
                    mapping["shift"], shift
                )

    async def _set_helper_if_changed(
        self, entity_id: str, value: float
    ) -> None:
        """Update a helper only when its value differs."""
        state = self.hass.states.get(entity_id)

        if state is None:
            _LOGGER.warning(
                "Configured helper %s does not exist",
                entity_id,
            )
            return

        try:
            current = float(state.state)
        except (TypeError, ValueError):
            current = None

        if current is not None and abs(current - value) < 0.0001:
            return

        attributes = state.attributes

        try:
            minimum = float(attributes.get("min", float("-inf")))
            maximum = float(attributes.get("max", float("inf")))
        except (TypeError, ValueError):
            minimum = float("-inf")
            maximum = float("inf")

        if not minimum <= value <= maximum:
            _LOGGER.warning(
                "ViCare value %s for %s is outside helper range %s to %s",
                value,
                entity_id,
                minimum,
                maximum,
            )
            return

        await self.hass.services.async_call(
            "input_number",
            "set_value",
            {
                "entity_id": entity_id,
                "value": value,
            },
            blocking=True,
        )

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
        async with self._lock:
            if self._stopped:
                return

            circuit = self.circuits[circuit_index]

            try:
                slope, shift = await self._read_curve(circuit_index)

                if changed_value == "slope":
                    if abs(slope - value) < 0.0001:
                        return

                    minimum, maximum = await self.hass.async_add_executor_job(
                        lambda: (
                            float(circuit.getHeatingCurveSlopeMin()),
                            float(circuit.getHeatingCurveSlopeMax()),
                        )
                    )

                    if not minimum <= value <= maximum:
                        _LOGGER.warning(
                            "Slope %s for circuit %s is outside ViCare limits %s to %s",
                            value,
                            circuit_index,
                            minimum,
                            maximum,
                        )
                        return

                    slope = value

                else:
                    if abs(shift - value) < 0.0001:
                        return

                    minimum, maximum = await self.hass.async_add_executor_job(
                        lambda: (
                            float(circuit.getHeatingCurveShiftMin()),
                            float(circuit.getHeatingCurveShiftMax()),
                        )
                    )

                    if not minimum <= value <= maximum:
                        _LOGGER.warning(
                            "Shift %s for circuit %s is outside ViCare limits %s to %s",
                            value,
                            circuit_index,
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

                _LOGGER.info(
                    "Updated ViCare circuit %s: slope=%s, shift=%s",
                    circuit_index,
                    slope,
                    shift,
                )

            except Exception:
                _LOGGER.exception(
                    "Could not write heating curve to ViCare circuit %s",
                    circuit_index,
                )

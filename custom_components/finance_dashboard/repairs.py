"""Repair flows for Finance.

Handles two fix flows:
- ``restart_required``: prompts HA restart after an integration update.
- ``initial_sync_pending``: triggers a 12-month history backfill.

Issues are raised directly via ``homeassistant.helpers.issue_registry`` inside
the manager because they have the full execution context at the point of need.
"""

from __future__ import annotations

from ha_customapps.repairs import RestartRepairFlow
from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant


class InitialSyncRepairFlow(RepairsFlow):
    """Repair flow that triggers a 12-month transaction backfill."""

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> data_entry_flow.FlowResult:
        """Show confirmation form, then kick off the full-history fetch."""
        if user_input is not None:
            from .const import DOMAIN, SERVICE_FETCH_FULL_HISTORY

            # Fire-and-forget: the fetch runs in the background so the flow
            # returns immediately and the Repairs UI stays responsive.
            self.hass.async_create_task(
                self.hass.services.async_call(
                    DOMAIN, SERVICE_FETCH_FULL_HISTORY, {}, blocking=False
                )
            )
            return self.async_create_entry(data={}, title="")
        return self.async_show_form(step_id="init")


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict | None
) -> RepairsFlow | None:
    """Route repair issues to their respective fix flows."""
    if issue_id == "restart_required":
        return RestartRepairFlow()
    if issue_id == "initial_sync_pending":
        return InitialSyncRepairFlow()
    return None

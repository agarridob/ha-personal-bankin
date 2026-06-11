"""Sidebar panel registration for Finance — uses ha-customapps PanelRegistrar."""

from __future__ import annotations

import logging

from ha_customapps.panel import PanelRegistrar
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    PANEL_COMPONENT_NAME,
    PANEL_ICON,
    PANEL_MODULE_PATH,
    PANEL_TITLE,
    PANEL_URL_PATH,
    VERSION,
)

_LOGGER = logging.getLogger(__name__)

STATIC_BASE = f"/api/{DOMAIN}/static"
# ?v= busts the 1h browser cache (Cache-Control on the static view) on updates
LOVELACE_COMPONENTS = [
    f"{STATIC_BASE}/{name}?v={VERSION}"
    for name in (
        "fd-shared-styles.js",
        "fd-data-provider.js",
        "fd-stat-card.js",
        "fd-person-card.js",
        "fd-donut-chart.js",
        "fd-header.js",
        "fd-stats-row.js",
        "fd-household-section.js",
        "fd-category-section.js",
        "fd-cost-distribution.js",
        "fd-recurring-list.js",
        "fd-transactions-log.js",
        "fd-budget-config.js",
        "fd-categorize.js",
        "fd-setup-wizard.js",
        "finance-status-chip.js",
    )
]


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register the Finance sidebar panel."""
    try:
        registrar = PanelRegistrar(
            hass=hass,
            domain=DOMAIN,
            panel_component=PANEL_COMPONENT_NAME,
            panel_title=PANEL_TITLE,
            panel_icon=PANEL_ICON,
            panel_url_path=PANEL_URL_PATH,
            module_url=PANEL_MODULE_PATH,
            frontend_dir=hass.config.path("custom_components", DOMAIN, "frontend"),
            lovelace_urls=LOVELACE_COMPONENTS,
        )
        await registrar.async_register()
        _LOGGER.debug("Finance panel registered at /%s", PANEL_URL_PATH)
    except Exception:
        _LOGGER.exception("Failed to register Finance panel")


async def async_unregister_panel(hass: HomeAssistant) -> None:
    """Unregister custom sidebar panel."""
    from homeassistant.components import panel_custom

    try:
        panel_custom.async_unregister_panel(hass, PANEL_URL_PATH)
    except Exception:
        _LOGGER.debug("Panel was not registered, nothing to remove")

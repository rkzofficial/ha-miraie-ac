"""Config flow for mirAIe integration."""
from __future__ import annotations

import logging
from datetime import date
import calendar
from typing import Any, Optional

from miraie_ac import MirAIeHub
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_INSTALL_DATE, DOMAIN

_LOGGER = logging.getLogger(__name__)

def months_ago(today: date, months: int) -> date:
    month = today.month - months
    year = today.year
    if month <= 0:
        month += 12
        year -= 1
    day = min(today.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def six_months_ago(today: date) -> date:
    return months_ago(today, 6)


def eight_months_ago(today: date) -> date:
    return months_ago(today, 8)


def parse_install_date(value: str) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise InvalidInstallDate from exc


def build_user_schema(default_install_date: str) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("username"): str,
            vol.Required("password"): str,
            vol.Optional(CONF_INSTALL_DATE, default=default_install_date): str,
        }
    )


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> tuple[dict[str, Any], Optional[date]]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    async with MirAIeHub() as hub:
        # pylint: disable=protected-access
        try:
            await hub._authenticate(data["username"], data["password"])
        except Exception as exc:
            raise InvalidAuth from exc

    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth

    # Return info that you want to store in the config entry.
    install_date = parse_install_date(data.get(CONF_INSTALL_DATE, ""))
    return {"title": "MirAIe"}, install_date


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for mirAIe."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            default_install = six_months_ago(date.today()).isoformat()
            return self.async_show_form(
                step_id="user", data_schema=build_user_schema(default_install)
            )

        errors = {}

        try:
            info, install_date = await validate_input(self.hass, user_input)
            today = date.today()
            min_date = six_months_ago(today)
            oldest_date = eight_months_ago(today)
            if install_date is None:
                install_date = min_date
            if install_date < oldest_date or install_date > today:
                errors[CONF_INSTALL_DATE] = "invalid_install_date"
                raise InvalidInstallDate
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except InvalidInstallDate:
            errors[CONF_INSTALL_DATE] = "invalid_install_date"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            options = {CONF_INSTALL_DATE: install_date.isoformat()}
            data = {k: v for k, v in user_input.items() if k != CONF_INSTALL_DATE}
            return self.async_create_entry(title=info["title"], data=data, options=options)

        return self.async_show_form(
            step_id="user",
            data_schema=build_user_schema(user_input.get(CONF_INSTALL_DATE, "")),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return OptionsFlowHandler(config_entry)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidInstallDate(HomeAssistantError):
    """Error to indicate invalid installation date."""


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for mirAIe."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is None:
            today = date.today()
            default_install = six_months_ago(today).isoformat()
            current = self.config_entry.options.get(CONF_INSTALL_DATE, default_install)
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                    {vol.Optional(CONF_INSTALL_DATE, default=current): str}
                ),
            )

        errors = {}
        try:
            install_date = parse_install_date(user_input.get(CONF_INSTALL_DATE, ""))
            today = date.today()
            min_date = six_months_ago(today)
            oldest_date = eight_months_ago(today)
            if install_date is None:
                install_date = min_date
            if install_date < oldest_date or install_date > today:
                errors[CONF_INSTALL_DATE] = "invalid_install_date"
                raise InvalidInstallDate
        except InvalidInstallDate:
            errors[CONF_INSTALL_DATE] = "invalid_install_date"
        else:
            return self.async_create_entry(
                title="",
                data={CONF_INSTALL_DATE: install_date.isoformat()},
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Optional(CONF_INSTALL_DATE, default=user_input.get(CONF_INSTALL_DATE, "")): str}
            ),
            errors=errors,
        )

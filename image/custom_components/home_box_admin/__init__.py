"""Home Box local owner create / password reset (enroll-token gated).

Passwords never come from BMS. BMS only sets allow_password_reset in the
subscription snapshot; the agent caches it under /config/bms_runtime.json.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from aiohttp import web

from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.auth.providers.homeassistant import HassAuthProvider, InvalidUser
from homeassistant.components.http import KEY_HASS
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "home_box_admin"
CONFIG = Path("/config")
ENROLL_PATH = CONFIG / "bms_enroll.json"
RUNTIME_PATH = CONFIG / "bms_runtime.json"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.http.register_view(OwnerStatusView())
    hass.http.register_view(OwnerCreateView())
    hass.http.register_view(PasswordResetView())
    return True


def _read_json_sync(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


async def _read_json(hass: HomeAssistant, path: Path) -> dict[str, Any]:
    return await hass.async_add_executor_job(_read_json_sync, path)


async def _enroll_token(hass: HomeAssistant) -> str:
    data = await _read_json(hass, ENROLL_PATH)
    return str(data.get("enroll_token") or "").strip()


async def _allow_password_reset(hass: HomeAssistant) -> bool:
    data = await _read_json(hass, RUNTIME_PATH)
    if "allow_password_reset" in data:
        return bool(data.get("allow_password_reset"))
    machine = data.get("machine") if isinstance(data.get("machine"), dict) else {}
    return bool(machine.get("allow_password_reset"))


async def _check_enroll_auth(hass: HomeAssistant, request: web.Request) -> str | None:
    expected = await _enroll_token(hass)
    if not expected:
        return "not_enrolled"
    header = request.headers.get("Authorization") or ""
    if not header.lower().startswith("bearer "):
        return "missing_bearer"
    if header[7:].strip() != expected:
        return "invalid_token"
    return None


async def _json_body(request: web.Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


async def _hass_provider(hass: HomeAssistant) -> HassAuthProvider | None:
    for provider in hass.auth.auth_providers:
        if provider.type == "homeassistant" and isinstance(provider, HassAuthProvider):
            return provider
    return None


class OwnerStatusView(HomeAssistantView):
    url = "/api/home_box/owner_status"
    name = "api:home_box:owner_status"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app[KEY_HASS]
        err = await _check_enroll_auth(hass, request)
        if err:
            return self.json({"ok": False, "error": err}, status=401)
        provider = await _hass_provider(hass)
        usernames: dict[str, str] = {}
        if provider:
            await provider.async_initialize()
        users_out = []
        for user in await hass.auth.async_get_users():
            if not user.is_active:
                continue
            username = None
            for cred in user.credentials:
                if cred.auth_provider_type == "homeassistant" and cred.data:
                    uname = cred.data.get("username")
                    if uname:
                        username = str(uname)
                        usernames[user.id] = username
            users_out.append(
                {
                    "id": user.id,
                    "name": user.name,
                    "is_owner": user.is_owner,
                    "is_admin": user.is_admin,
                    "username": username or usernames.get(user.id),
                }
            )
        return self.json(
            {
                "ok": True,
                "enrolled": True,
                "allow_password_reset": await _allow_password_reset(hass),
                "has_owner": any(u.get("is_owner") for u in users_out),
                "users": users_out,
            }
        )


class OwnerCreateView(HomeAssistantView):
    url = "/api/home_box/owner"
    name = "api:home_box:owner"
    requires_auth = False

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app[KEY_HASS]
        err = await _check_enroll_auth(hass, request)
        if err:
            return self.json({"ok": False, "error": err}, status=401)

        if any(u.is_owner for u in await hass.auth.async_get_users() if u.is_active):
            return self.json(
                {
                    "ok": False,
                    "error": "owner_exists",
                    "hint": "Use password reset when BMS enables Allow Home Box password reset.",
                },
                status=409,
            )

        data = await _json_body(request)
        name = str(data.get("name") or "").strip()
        username = str(data.get("username") or "").strip().lower()
        password = str(data.get("password") or "")
        if not name or not username or len(password) < 8:
            return self.json(
                {
                    "ok": False,
                    "error": "invalid_input",
                    "hint": "name, username, password (min 8 chars) required",
                },
                status=400,
            )

        provider = await _hass_provider(hass)
        if not provider:
            return self.json({"ok": False, "error": "no_auth_provider"}, status=500)

        await provider.async_initialize()
        try:
            await provider.async_add_auth(username, password)
        except Exception as exc:  # noqa: BLE001
            return self.json(
                {"ok": False, "error": "create_failed", "detail": str(exc)}, status=400
            )

        credentials = await provider.async_get_or_create_credentials({"username": username})
        user = await hass.auth.async_get_user_by_credentials(credentials)
        if user is None:
            user = await hass.auth.async_create_user(name, group_ids=[GROUP_ID_ADMIN])
            await hass.auth.async_link_user(user, credentials)

        kwargs: dict[str, Any] = {"name": name, "group_ids": [GROUP_ID_ADMIN]}
        try:
            await hass.auth.async_update_user(user, **kwargs, is_owner=True)
        except TypeError:
            await hass.auth.async_update_user(user, **kwargs)

        _LOGGER.info("home_box_admin created owner username=%s", username)
        return self.json(
            {
                "ok": True,
                "username": username,
                "name": name,
                "note": "Password stays on this Home Box only — not sent to BMS.",
            }
        )


class PasswordResetView(HomeAssistantView):
    url = "/api/home_box/password_reset"
    name = "api:home_box:password_reset"
    requires_auth = False

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app[KEY_HASS]
        err = await _check_enroll_auth(hass, request)
        if err:
            return self.json({"ok": False, "error": err}, status=401)
        if not await _allow_password_reset(hass):
            return self.json(
                {
                    "ok": False,
                    "error": "reset_disabled",
                    "hint": "Ask BMS staff to turn on Allow Home Box password reset.",
                },
                status=403,
            )

        data = await _json_body(request)
        username = str(data.get("username") or "").strip().lower()
        password = str(data.get("password") or "")
        if not username or len(password) < 8:
            return self.json(
                {
                    "ok": False,
                    "error": "invalid_input",
                    "hint": "username and password (min 8 chars) required",
                },
                status=400,
            )

        provider = await _hass_provider(hass)
        if not provider:
            return self.json({"ok": False, "error": "no_auth_provider"}, status=500)

        await provider.async_initialize()
        try:
            await provider.async_change_password(username, password)
        except InvalidUser:
            return self.json({"ok": False, "error": "unknown_username"}, status=404)
        except Exception as exc:  # noqa: BLE001
            return self.json(
                {"ok": False, "error": "reset_failed", "detail": str(exc)}, status=400
            )

        _LOGGER.info("home_box_admin password reset username=%s", username)
        return self.json(
            {
                "ok": True,
                "username": username,
                "note": "New password is only on this Home Box. BMS staff can turn the reset switch off.",
            }
        )

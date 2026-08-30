"""Home Box local owner create / password reset (enroll-token gated).

QR may include one-time admin credentials (bootstrap=true on create).
Passwords are not returned to BMS. BMS only sets allow_password_reset in the
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
from homeassistant.components.http import KEY_HASS, KEY_HASS_USER
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "home_box_admin"
CONFIG = Path("/config")
ENROLL_PATH = CONFIG / "bms_enroll.json"
RUNTIME_PATH = CONFIG / "bms_runtime.json"
SHARE_PATH = CONFIG / "bms_share.json"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.http.register_view(OwnerStatusView())
    hass.http.register_view(OwnerCreateView())
    hass.http.register_view(PasswordResetView())
    hass.http.register_view(LimitedShareView())
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
            return self.json({"ok": False, "error": err}, status_code=401)
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
            return self.json({"ok": False, "error": err}, status_code=401)

        data = await _json_body(request)
        name = str(data.get("name") or "").strip()
        username = str(data.get("username") or "").strip().lower()
        password = str(data.get("password") or "")
        bootstrap = bool(data.get("bootstrap"))
        if not name or not username or len(password) < 8:
            return self.json(
                {
                    "ok": False,
                    "error": "invalid_input",
                    "hint": "name, username, password (min 8 chars) required",
                },
                status_code=400,
            )

        owner_exists = any(
            u.is_owner for u in await hass.auth.async_get_users() if u.is_active
        )
        if owner_exists and not bootstrap:
            return self.json(
                {
                    "ok": False,
                    "error": "owner_exists",
                    "hint": "Use password reset when BMS enables Allow Home Box password reset.",
                },
                status_code=409,
            )

        provider = await _hass_provider(hass)
        if not provider:
            return self.json({"ok": False, "error": "no_auth_provider"}, status_code=500)

        await provider.async_initialize()

        # One-time QR bootstrap: set/replace credentials even if an owner already exists.
        if owner_exists and bootstrap:
            try:
                await provider.async_change_password(username, password)
                _LOGGER.info("home_box_admin bootstrap password updated username=%s", username)
                return self.json(
                    {
                        "ok": True,
                        "username": username,
                        "name": name,
                        "bootstrap": True,
                        "note": "Password updated from QR bootstrap.",
                    }
                )
            except InvalidUser:
                pass
            except Exception as exc:  # noqa: BLE001
                return self.json(
                    {"ok": False, "error": "bootstrap_failed", "detail": str(exc)},
                    status_code=400,
                )

            try:
                await provider.async_add_auth(username, password)
            except Exception as exc:  # noqa: BLE001
                return self.json(
                    {"ok": False, "error": "create_failed", "detail": str(exc)},
                    status_code=400,
                )
            credentials = await provider.async_get_or_create_credentials(
                {"username": username}
            )
            owner = next(
                (u for u in await hass.auth.async_get_users() if u.is_active and u.is_owner),
                None,
            )
            if owner is not None:
                await hass.auth.async_link_user(owner, credentials)
                kwargs: dict[str, Any] = {"name": name, "group_ids": [GROUP_ID_ADMIN]}
                try:
                    await hass.auth.async_update_user(owner, **kwargs, is_owner=True)
                except TypeError:
                    await hass.auth.async_update_user(owner, **kwargs)
            _LOGGER.info("home_box_admin bootstrap linked username=%s", username)
            return self.json(
                {
                    "ok": True,
                    "username": username,
                    "name": name,
                    "bootstrap": True,
                    "note": "QR admin username linked to existing owner.",
                }
            )

        try:
            await provider.async_add_auth(username, password)
        except Exception as exc:  # noqa: BLE001
            return self.json(
                {"ok": False, "error": "create_failed", "detail": str(exc)}, status_code=400
            )

        credentials = await provider.async_get_or_create_credentials({"username": username})
        user = await hass.auth.async_get_user_by_credentials(credentials)
        if user is None:
            user = await hass.auth.async_create_user(name, group_ids=[GROUP_ID_ADMIN])
            await hass.auth.async_link_user(user, credentials)

        kwargs = {"name": name, "group_ids": [GROUP_ID_ADMIN]}
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
                "note": "Password stays on this Home Box only â€” not sent to BMS.",
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
            return self.json({"ok": False, "error": err}, status_code=401)
        if not await _allow_password_reset(hass):
            return self.json(
                {
                    "ok": False,
                    "error": "reset_disabled",
                    "hint": "Ask BMS staff to turn on Allow Home Box password reset.",
                },
                status_code=403,
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
                status_code=400,
            )

        provider = await _hass_provider(hass)
        if not provider:
            return self.json({"ok": False, "error": "no_auth_provider"}, status_code=500)

        await provider.async_initialize()
        try:
            await provider.async_change_password(username, password)
        except InvalidUser:
            return self.json({"ok": False, "error": "unknown_username"}, status_code=404)
        except Exception as exc:  # noqa: BLE001
            return self.json(
                {"ok": False, "error": "reset_failed", "detail": str(exc)}, status_code=400
            )

        _LOGGER.info("home_box_admin password reset username=%s", username)
        return self.json(
            {
                "ok": True,
                "username": username,
                "note": "New password is only on this Home Box. BMS staff can turn the reset switch off.",
            }
        )


def _share_sync_load() -> dict[str, Any]:
    data = _read_json_sync(SHARE_PATH)
    return {
        "limited_share_enabled": bool(data.get("limited_share_enabled")),
        "scope": list(data.get("scope") or ["status", "support_activity"]),
        "updated_at": data.get("updated_at"),
    }


def _share_sync_save(enabled: bool) -> dict[str, Any]:
    from datetime import datetime, timezone

    body = {
        "v": 1,
        "limited_share_enabled": bool(enabled),
        "scope": ["status", "support_activity"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Box consent only. No company sees data until the homeowner "
            "grants a limited share to that company in BMS."
        ),
    }
    SHARE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SHARE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    tmp.replace(SHARE_PATH)
    return body


class LimitedShareView(HomeAssistantView):
    """Owner toggle for limited share consent (status + support activity).

    Does not grant any company. BMS ShareGrant is a separate step.
    """

    url = "/api/home_box/limited_share"
    name = "api:home_box:limited_share"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app[KEY_HASS]
        user = request[KEY_HASS_USER]
        if user is None or not user.is_admin:
            return self.json({"ok": False, "error": "admin_required"}, status_code=403)
        share = await hass.async_add_executor_job(_share_sync_load)
        runtime = await _read_json(hass, RUNTIME_PATH)
        grants = runtime.get("shares") if isinstance(runtime.get("shares"), list) else []
        return self.json(
            {
                "ok": True,
                **share,
                "active_company_grants": grants,
                "note": (
                    "Turning this on only allows limited status/support data to leave the box "
                    "toward BMS. No company sees it until you grant them in BMS."
                ),
            }
        )

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app[KEY_HASS]
        user = request[KEY_HASS_USER]
        if user is None or not user.is_admin:
            return self.json({"ok": False, "error": "admin_required"}, status_code=403)
        data = await _json_body(request)
        if "enabled" not in data:
            return self.json(
                {"ok": False, "error": "invalid_input", "hint": "JSON {\"enabled\": true|false}"},
                status_code=400,
            )
        enabled = bool(data.get("enabled"))
        body = await hass.async_add_executor_job(_share_sync_save, enabled)
        _LOGGER.info("home_box_admin limited_share_enabled=%s", enabled)
        return self.json({"ok": True, **body})

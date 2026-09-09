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
SHARE_PATH = CONFIG / "bms_share.json"
RUNTIME_PATH = CONFIG / "bms_runtime.json"
SECRETS_PATH = CONFIG / "secrets.yaml"
DEFAULT_BMS_PORTAL_URL = "https://bms.scardustech.com/portal"


def _bms_manage_url() -> str:
    """Public BMS URL where the homeowner manages company share grants."""
    import os
    import re

    env = str(os.environ.get("BMS_PORTAL_URL") or "").strip().rstrip("/")
    if env:
        return env
    if SECRETS_PATH.is_file():
        try:
            text = SECRETS_PATH.read_text(encoding="utf-8")
        except Exception:
            text = ""
        match = re.search(
            r"(?m)^\s*bms_portal_url\s*:\s*[\"']?([^\"'\n#]+?)[\"']?\s*(?:#.*)?$",
            text,
        )
        if match:
            return str(match.group(1) or "").strip().rstrip("/")
    return DEFAULT_BMS_PORTAL_URL


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
    raw = data.get("sensors")
    if raw is None:
        raw = data.get("sensor_entities")
    sensors: list[dict[str, str]] = []
    seen: set[str] = set()
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                eid = item.strip().lower()
                system = ""
            elif isinstance(item, dict):
                eid = str(item.get("entity_id") or "").strip().lower()
                system = str(item.get("system") or item.get("domain") or "").strip().lower()
            else:
                continue
            if not eid.startswith("binary_sensor.") or eid in seen:
                continue
            seen.add(eid)
            sensors.append({"entity_id": eid, "system": system})
    cats: list[str] = []
    cat_seen: set[str] = set()
    for item in data.get("categories") if isinstance(data.get("categories"), list) else []:
        slug = str(item or "").strip().lower().replace(" ", "-")
        slug = "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in slug)
        while "--" in slug:
            slug = slug.replace("--", "-")
        slug = slug.strip("-")
        if not slug or slug in cat_seen:
            continue
        cat_seen.add(slug)
        cats.append(slug)
    for row in sensors:
        slug = str(row.get("system") or "").strip()
        if slug and slug not in cat_seen:
            cat_seen.add(slug)
            cats.append(slug)
    cats.sort()
    return {
        "limited_share_enabled": bool(data.get("limited_share_enabled")),
        "scope": list(data.get("scope") or ["status", "support_activity", "sensors"]),
        "categories": cats,
        "sensors": sensors,
        "sensor_entities": [s["entity_id"] for s in sensors],
        "updated_at": data.get("updated_at"),
    }


def _share_sync_save(
    enabled: bool,
    sensors: list[Any] | None = None,
    categories: list[Any] | None = None,
) -> dict[str, Any]:
    from datetime import datetime, timezone

    current = _share_sync_load()
    if sensors is None:
        entries = list(current.get("sensors") or [])
    else:
        entries = []
        seen: set[str] = set()
        for item in sensors:
            if isinstance(item, str):
                eid = item.strip().lower()
                system = ""
            elif isinstance(item, dict):
                eid = str(item.get("entity_id") or "").strip().lower()
                system = str(item.get("system") or item.get("domain") or "").strip().lower()
            else:
                continue
            if not eid.startswith("binary_sensor.") or eid in seen:
                continue
            seen.add(eid)
            entries.append({"entity_id": eid, "system": system})
    if categories is None:
        cat_raw = current.get("categories") or []
    else:
        cat_raw = categories
    cats: list[str] = []
    cat_seen: set[str] = set()
    for item in cat_raw if isinstance(cat_raw, list) else []:
        slug = str(item or "").strip().lower().replace(" ", "-")
        slug = "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in slug)
        while "--" in slug:
            slug = slug.replace("--", "-")
        slug = slug.strip("-")
        if not slug or slug in cat_seen:
            continue
        cat_seen.add(slug)
        cats.append(slug)
    for row in entries:
        slug = str(row.get("system") or "").strip()
        if slug and slug not in cat_seen:
            cat_seen.add(slug)
            cats.append(slug)
    cats.sort()
    body = {
        "v": 2,
        "limited_share_enabled": bool(enabled),
        "scope": ["status", "support_activity", "sensors"],
        "categories": cats,
        "sensors": entries,
        "sensor_entities": [s["entity_id"] for s in entries],
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Box consent only. Client labels each sensor (domain or location). "
            "No company sees data until the homeowner grants them in BMS."
        ),
    }
    SHARE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SHARE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    tmp.replace(SHARE_PATH)
    return body


def _available_binary_sensors(hass: HomeAssistant) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for state in hass.states.async_all("binary_sensor"):
        eid = state.entity_id
        attrs = state.attributes or {}
        rows.append(
            {
                "entity_id": eid,
                "name": attrs.get("friendly_name") or eid,
                "state": state.state,
                "device_class": attrs.get("device_class"),
            }
        )
    rows.sort(key=lambda r: str(r.get("entity_id") or ""))
    return rows


class LimitedShareView(HomeAssistantView):
    """Owner toggle for limited sensory share (status + selected binary sensors).

    Does not grant any company. BMS ShareGrant is a separate step.
    Never exposes switches / relays for sharing.
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
        household = (
            runtime.get("household") if isinstance(runtime.get("household"), dict) else {}
        )
        manage_url = await hass.async_add_executor_job(_bms_manage_url)
        return self.json(
            {
                "ok": True,
                **share,
                "available_sensors": _available_binary_sensors(hass),
                "bms_manage_url": manage_url,
                "household_name": household.get("name") or household.get("slug") or "",
                "household_slug": household.get("slug") or "",
                "note": (
                    "Create categories, select sensors, assign a category to each, then Save. "
                    "Home Box never invents labels. Manage which companies see data in BMS. "
                    "Switches/relays are never shared."
                ),
            }
        )

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app[KEY_HASS]
        user = request[KEY_HASS_USER]
        if user is None or not user.is_admin:
            return self.json({"ok": False, "error": "admin_required"}, status_code=403)
        data = await _json_body(request)
        if (
            "enabled" not in data
            and "sensors" not in data
            and "sensor_entities" not in data
            and "categories" not in data
        ):
            return self.json(
                {
                    "ok": False,
                    "error": "invalid_input",
                    "hint": (
                        'JSON {"enabled": true|false, "categories": ["hvac","kitchen"], '
                        '"sensors": [{"entity_id":"binary_sensor.…","system":"hvac"}]}'
                    ),
                },
                status_code=400,
            )
        current = await hass.async_add_executor_job(_share_sync_load)
        enabled = (
            bool(data.get("enabled"))
            if "enabled" in data
            else bool(current.get("limited_share_enabled"))
        )
        sensors = data.get("sensors") if "sensors" in data else data.get("sensor_entities")
        if "sensors" not in data and "sensor_entities" not in data:
            sensors = None
        if sensors is not None and not isinstance(sensors, list):
            return self.json(
                {"ok": False, "error": "invalid_input", "hint": "sensors must be a list"},
                status_code=400,
            )
        categories = data.get("categories") if "categories" in data else None
        if categories is not None and not isinstance(categories, list):
            return self.json(
                {"ok": False, "error": "invalid_input", "hint": "categories must be a list"},
                status_code=400,
            )
        body = await hass.async_add_executor_job(
            _share_sync_save, enabled, sensors, categories
        )
        _LOGGER.info(
            "home_box_admin limited_share_enabled=%s sensors=%s categories=%s",
            enabled,
            len(body.get("sensors") or []),
            len(body.get("categories") or []),
        )
        return self.json({"ok": True, **body})

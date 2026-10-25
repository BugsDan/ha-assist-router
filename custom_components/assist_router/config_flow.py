"""HA UI: sortable entities, activation, positions and optional per-agent probes."""

from copy import deepcopy
from dataclasses import asdict

import probatio as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .const import DOMAIN
from .health_types import CHECK_TYPES
from .prompts import NEUTRAL_BASELINE, PromptManager, async_make_inspector
from .settings import HealthSettings, PromptSettings, Settings, valid_agent_id, validate_prompt_text


def entity_selector(excluded=(), included=None, multiple=False, reorder=False):
    config = {
        "filter": {"domain": "conversation"},
        "exclude_entities": list(excluded),
        "multiple": multiple,
        "reorder": reorder,
    }
    if included is not None:
        config["include_entities"] = list(included)
    return selector.EntitySelector(selector.EntitySelectorConfig(**config))


def choice(options, translation_key=None):
    config = {"options": options, "sort": False}
    if translation_key:
        config["translation_key"] = translation_key
    return selector.SelectSelector(selector.SelectSelectorConfig(**config))


def merge_health(previous, user_input, kind):
    """Never put secrets into form defaults. Blank retains only at the same endpoint."""
    values = {**previous, **user_input, "kind": kind}
    retain = previous.get("url") == values.get("url") and previous.get("auth_type", "none") == values.get(
        "auth_type", "none"
    )
    for secret in ("token", "password"):
        if not user_input.get(secret):
            values[secret] = previous.get(secret, "") if retain else ""
    if user_input.get("clear_credentials"):
        values.update(token="", password="", username="", auth_type="none")
    values.pop("clear_credentials", None)
    # HTTP has no model readiness predicate, even after switching from LM Studio.
    if not CHECK_TYPES[kind].uses_model:
        for key in ("model_key", "instance_id", "model_state"):
            values.pop(key, None)
    return asdict(HealthSettings.from_mapping(values))


def health_schema(values, kind):
    defaults = {
        "url": "",
        "timeout": 1.0,
        "cache_seconds": 2.0,
        "failure_cache_seconds": 15.0,
        "expected_status": 200,
        "auth_type": "none",
        "username": "",
        "model_key": "",
        "instance_id": "",
        "model_state": "loaded",
        **values,
    }
    schema = {
        vol.Required("url", default=defaults["url"]): selector.TextSelector(),
        vol.Required("auth_type", default=defaults["auth_type"]): choice(
            ["none", "bearer", "basic"], "auth_type"
        ),
        vol.Optional("username", default=defaults["username"]): selector.TextSelector(),
        vol.Optional("clear_credentials", default=False): selector.BooleanSelector(),
    }
    for secret in ("token", "password"):
        schema[vol.Optional(secret)] = selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        )
    for key, lower, upper, coerce in (
        ("timeout", 0.1, 3, float),
        ("cache_seconds", 0, 5, float),
        ("failure_cache_seconds", 0, 60, float),
        ("expected_status", 200, 299, int),
    ):
        schema[vol.Required(key, default=defaults[key])] = vol.All(
            vol.Coerce(coerce), vol.Range(min=lower, max=upper)
        )
    if CHECK_TYPES[kind].uses_model:
        schema[vol.Required("model_key", default=defaults["model_key"])] = selector.TextSelector()
        schema[vol.Optional("instance_id", default=defaults["instance_id"])] = selector.TextSelector()
        schema[vol.Required("model_state", default=defaults["model_state"])] = choice(
            ["loaded", "present"], "model_state"
        )
    return vol.Schema(schema)


class RoutingFlow:
    """Draft only: persist once on Finish; cancelling any step leaves the entry intact."""

    def _start(self, config):
        self._draft = deepcopy(config)
        self._draft.setdefault("prompt", asdict(PromptSettings()))
        self._health_agent = None
        self._health_kind = None
        self._prompt_agent = None
        self._inspector = None

    def _excluded(self):
        registry = er.async_get(self.hass)
        return [
            "conversation.home_assistant",
            *[item.entity_id for item in registry.entities.values() if item.platform == DOMAIN],
        ]

    def _ids(self):
        return [item["entity_id"] for item in self._draft["agents"]]

    def _menu(self):
        summary = "\n".join(
            f"{i}. {item['entity_id']} ({'✓' if item['enabled'] else '–'}; "
            f"{(item.get('health') or {}).get('kind', 'entity')})"
            for i, item in enumerate(self._draft["agents"], 1)
        )
        return self.async_show_menu(
            step_id="manage",
            menu_options=[
                "order",
                "position",
                "enabled",
                "health_agent",
                "shared_prompt",
                "agent_prompt",
                "prompt_review",
                "finish",
            ],
            description_placeholders={"agents": summary},
        )

    async def async_step_manage(self, user_input=None):
        return self._menu()

    async def async_step_order(self, user_input=None):
        errors = {}
        if user_input is not None:
            order = user_input.get("agent_order")
            if (
                not isinstance(order, list)
                or not order
                or any(not valid_agent_id(value) or value in self._excluded() for value in order)
                or len(order) != len(set(order))
            ):
                errors["base"] = "invalid_agents"
            else:
                existing = {item["entity_id"]: item for item in self._draft["agents"]}
                draft = {
                    **self._draft,
                    "agents": [
                        deepcopy(
                            existing.get(entity_id, {"entity_id": entity_id, "enabled": True, "health": None})
                        )
                        for entity_id in order
                    ],
                }
                try:
                    Settings.from_mapping(draft)
                except ValueError as err:
                    errors["base"] = str(err)
                else:
                    self._draft = draft
                    return self._menu()
        return self.async_show_form(
            step_id="order",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("agent_order", default=self._ids()): entity_selector(
                        self._excluded(), multiple=True, reorder=True
                    )
                }
            ),
        )

    async def async_step_position(self, user_input=None):
        if not self._ids():
            return await self.async_step_order()
        errors = {}
        if user_input is not None:
            entity_id, position = user_input.get("entity_id"), user_input.get("position")
            if (
                entity_id not in self._ids()
                or type(position) is not int
                or not 1 <= position <= len(self._ids())
            ):
                errors["base"] = "invalid_position"
            else:
                item = self._draft["agents"].pop(self._ids().index(entity_id))
                self._draft["agents"].insert(position - 1, item)
                return self._menu()
        return self.async_show_form(
            step_id="position",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("entity_id"): entity_selector(included=self._ids()),
                    vol.Required("position", default=1): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=len(self._ids()))
                    ),
                }
            ),
        )

    async def async_step_enabled(self, user_input=None):
        errors = {}
        if user_input is not None:
            enabled = user_input.get("enabled_agents")
            if not isinstance(enabled, list) or not enabled:
                errors["base"] = "no_active_agents"
            elif len(enabled) != len(set(enabled)) or any(value not in self._ids() for value in enabled):
                errors["base"] = "invalid_agents"
            else:
                for item in self._draft["agents"]:
                    item["enabled"] = item["entity_id"] in enabled
                return self._menu()
        return self.async_show_form(
            step_id="enabled",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "enabled_agents",
                        default=[item["entity_id"] for item in self._draft["agents"] if item["enabled"]],
                    ): entity_selector(included=self._ids(), multiple=True)
                }
            ),
        )

    async def async_step_health_agent(self, user_input=None):
        errors = {}
        if user_input is not None:
            if user_input.get("entity_id") not in self._ids():
                errors["base"] = "invalid_agents"
            else:
                self._health_agent = user_input["entity_id"]
                return await self.async_step_health_type()
        return self.async_show_form(
            step_id="health_agent",
            errors=errors,
            data_schema=vol.Schema({vol.Required("entity_id"): entity_selector(included=self._ids())}),
        )

    def _route(self):
        return next(item for item in self._draft["agents"] if item["entity_id"] == self._health_agent)

    async def async_step_health_type(self, user_input=None):
        errors = {}
        if user_input is not None:
            kind = user_input.get("kind")
            if kind == "none":
                self._route()["health"] = None
                return self._menu()
            if kind not in CHECK_TYPES:
                errors["base"] = "invalid_health"
            else:
                self._health_kind = kind
                return await self.async_step_health()
        current = self._route().get("health") or {}
        return self.async_show_form(
            step_id="health_type",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("kind", default=current.get("kind", "none")): choice(
                        ["none", *CHECK_TYPES], "check_kind"
                    )
                }
            ),
        )

    async def async_step_health(self, user_input=None):
        previous = self._route().get("health") or {}
        errors = {}
        if user_input is not None:
            try:
                result = merge_health(previous, user_input, self._health_kind)
            except ValueError as err:
                errors["base"] = str(err)
            else:
                self._route()["health"] = result
                return self._menu()
        # Submitted passwords/tokens are never echoed back after validation errors.
        return self.async_show_form(
            step_id="health", errors=errors, data_schema=health_schema(previous, self._health_kind)
        )

    async def async_step_shared_prompt(self, user_input=None):
        errors = {}
        values = self._draft["prompt"]
        if user_input is not None:
            values = {
                **values,
                "enabled": user_input.get("enabled", False),
                "text": user_input.get("text", ""),
            }
            try:
                PromptSettings.from_mapping(values)
                if values["enabled"] and user_input.get("acknowledge_additive") is not True:
                    raise ValueError("acknowledge_additive")
            except ValueError as err:
                errors["base"] = str(err)
            else:
                self._draft["prompt"] = values
                return self._menu()
        return self.async_show_form(
            step_id="shared_prompt",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("enabled", default=values["enabled"]): selector.BooleanSelector(),
                    vol.Optional("text", default=values["text"]): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    ),
                    vol.Required("acknowledge_additive", default=False): selector.BooleanSelector(),
                }
            ),
        )

    async def async_step_agent_prompt(self, user_input=None):
        errors = {}
        if user_input is not None:
            if user_input.get("entity_id") not in self._ids():
                errors["base"] = "invalid_agents"
            else:
                self._prompt_agent = user_input["entity_id"]
                return await self.async_step_agent_prompt_text()
        return self.async_show_form(
            step_id="agent_prompt",
            errors=errors,
            data_schema=vol.Schema({vol.Required("entity_id"): entity_selector(included=self._ids())}),
        )

    async def async_step_agent_prompt_text(self, user_input=None):
        route = next(item for item in self._draft["agents"] if item["entity_id"] == self._prompt_agent)
        errors = {}
        text = route.get("prompt_addition", "")
        if user_input is not None:
            text = user_input.get("text", "")
            try:
                validate_prompt_text(text)
            except ValueError as err:
                errors["base"] = str(err)
            else:
                route["prompt_addition"] = text
                return self._menu()
        return self.async_show_form(
            step_id="agent_prompt_text",
            errors=errors,
            description_placeholders={"agent": self._prompt_agent},
            data_schema=vol.Schema(
                {
                    vol.Optional("text", default=text): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    )
                }
            ),
        )

    async def async_step_prompt_review(self, user_input=None):
        errors = {}
        if user_input is not None:
            if user_input.get("entity_id") not in self._ids():
                errors["base"] = "invalid_agents"
            else:
                self._prompt_agent = user_input["entity_id"]
                self._review_snapshot = None
                return await self.async_step_prompt_review_confirm()
        return self.async_show_form(
            step_id="prompt_review",
            errors=errors,
            data_schema=vol.Schema({vol.Required("entity_id"): entity_selector(included=self._ids())}),
        )

    async def _get_inspector(self):
        if self._inspector is None:
            self._inspector = await async_make_inspector(self.hass)
        return self._inspector

    async def async_step_prompt_review_confirm(self, user_input=None):
        snapshot = await (await self._get_inspector()).inspect(self._prompt_agent)
        errors = {}
        if user_input is not None:
            if not snapshot.ready:
                errors["base"] = "prompt_not_compatible"
            elif self._review_snapshot is None or snapshot.fingerprint != self._review_snapshot.fingerprint:
                errors["base"] = "prompt_changed"
            elif user_input.get("confirm") is not True:
                errors["base"] = "prompt_confirm_required"
            else:
                self._draft["prompt"]["reviews"][self._prompt_agent] = snapshot.fingerprint
                return self._menu()
        self._review_snapshot = snapshot
        return self.async_show_form(
            step_id="prompt_review_confirm",
            errors=errors,
            description_placeholders={
                "agent": self._prompt_agent,
                "status": snapshot.reason,
                "fingerprint": snapshot.fingerprint or "–",
                "domain": snapshot.domain or "–",
                "sources": "; ".join(
                    f"{name}: {digest}" for name, digest in snapshot.source_fingerprints.items()
                )
                or "–",
            },
            data_schema=vol.Schema(
                {
                    vol.Optional("neutral_baseline", default=NEUTRAL_BASELINE): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True, read_only=True)
                    ),
                    vol.Required("confirm", default=False): selector.BooleanSelector(),
                }
            ),
        )

    async def async_step_finish(self, user_input=None):
        try:
            config = Settings.from_mapping(self._draft).as_dict()
        except ValueError:
            return await self.async_step_enabled({"enabled_agents": []})
        if any(item["entity_id"] in self._excluded() for item in config["agents"]):
            return await self.async_step_order({"agent_order": []})
        if config["prompt"]["enabled"]:
            manager = PromptManager(Settings.from_mapping(config), await self._get_inspector())
            if not await manager.validate():
                form = await self.async_step_prompt_review()
                form["errors"] = {"base": "prompt_review_required"}
                return form
        return self._save(config)


class ConfigFlow(RoutingFlow, config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 3
    MINOR_VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        self._start({"agents": []})
        return await self.async_step_order(user_input)

    def _save(self, config):
        return self.async_create_entry(title="Assist Router", data={}, options=config)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlow()


class OptionsFlow(RoutingFlow, config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        self._start(Settings.from_mapping({**self.config_entry.data, **self.config_entry.options}).as_dict())
        return self._menu()

    def _save(self, config):
        return self.async_create_entry(title="", data=config)

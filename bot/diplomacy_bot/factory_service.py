from __future__ import annotations

"""Geriye uyumluluk — yeni mantık modules.factory içinde."""

from typing import Any, Callable

from .account_config import AccountConfig, get_config
from .game_api import get_profile
from .modules import factory as factory_mod

ApiFn = Callable[..., tuple[int, Any]]


def factory_in_province(token: str, *, _api: ApiFn | None = None) -> str | None:
    api_fn = _api or factory_mod.default_api
    return factory_mod.factory_in_province(token, _api=api_fn)


def ensure_factory(token: str, *, _api: ApiFn | None = None, build_name: str = "BotFarm") -> str | None:
    api_fn = _api or factory_mod.default_api
    cfg = AccountConfig(account_name="_legacy", work_mode="auto", allow_auto_build=True)
    fid, err = factory_mod.resolve_factory_id(token, cfg, _api=api_fn)
    if fid:
        return fid
    if err and "kurulamadı" in err:
        return factory_mod.build_factory(token, build_name, _api=api_fn)
    return factory_mod.build_factory(token, build_name, _api=api_fn)


def prepare_join(token: str, factory_id: str, *, _api: ApiFn | None = None, build_suffix: str = "2") -> str:
    api_fn = _api or factory_mod.default_api
    cfg = AccountConfig(account_name="_legacy", work_mode="auto", allow_auto_build=True)
    fid, err = factory_mod.prepare_join(token, factory_id, cfg, _api=api_fn, build_suffix=build_suffix)
    return fid


def use_pills_if_needed(token: str, *, _api: ApiFn | None = None) -> dict | None:
    api_fn = _api or factory_mod.default_api
    return factory_mod.use_pills_if_needed(token, _api=api_fn)


def run_work_cycle(
    token: str,
    factory_id: str | None = None,
    *,
    _api: ApiFn | None = None,
    account_name: str | None = None,
) -> dict:
    api_fn = _api or factory_mod.default_api
    cfg = get_config(account_name) if account_name else AccountConfig(account_name="_legacy", work_mode="auto", allow_auto_build=True)
    return factory_mod.run_work_cycle(token, cfg, factory_id, _api=api_fn)

"""API yanıt sözleşmesi doğrulama."""
from __future__ import annotations

from typing import Any

from .api_route_registry import ApiRouteSpec


class ContractError(Exception):
    def __init__(self, route_id: str, reason: str, *, status: int | None = None, sample: Any = None):
        self.route_id = route_id
        self.reason = reason
        self.status = status
        self.sample = sample
        super().__init__(f"{route_id}: {reason}")


def _is_dict(data: Any) -> bool:
    return isinstance(data, dict)


def _has_any_key(data: dict, keys: tuple[str, ...]) -> bool:
    if not keys:
        return True
    return any(k in data for k in keys)


def _has_all_keys(data: dict, keys: tuple[str, ...]) -> bool:
    return all(k in data for k in keys)


def validate_response(spec: ApiRouteSpec, status: int, data: Any) -> None:
    """Başarılı veya beklenen hata yanıtını doğrula. ContractError fırlatır."""
    ok_status = status in spec.accept_status
    optional_miss = spec.optional and status == 404

    if status in (401, 403):
        if _is_dict(data) and ("error" in data or "message" in data):
            return
        raise ContractError(spec.route_id, f"auth hatası şekilsiz (status={status})", status=status, sample=data)

    if optional_miss:
        return

    if status == 429:
        if _is_dict(data):
            return
        raise ContractError(spec.route_id, "429 yanıtı dict değil", status=status)

    if status >= 400 and not ok_status:
        # İş kuralı hatası (cooldown, yetki) — dict olmalı
        if _is_dict(data) and ("error" in data or "message" in data or "remaining_ms" in data):
            return
        raise ContractError(
            spec.route_id,
            f"beklenmeyen hata status={status}",
            status=status,
            sample=data,
        )

    if not ok_status:
        raise ContractError(spec.route_id, f"status {status} ∉ {spec.accept_status}", status=status)

    if data is None:
        if status in (200, 201, 204):
            return
        raise ContractError(spec.route_id, "boş gövde", status=status)

    if not _is_dict(data):
        raise ContractError(spec.route_id, f"yanıt dict değil: {type(data).__name__}", status=status)

    if spec.all_keys and not _has_all_keys(data, spec.all_keys):
        missing = [k for k in spec.all_keys if k not in data]
        raise ContractError(spec.route_id, f"eksik anahtarlar: {missing}", status=status, sample=list(data.keys())[:12])

    if spec.any_keys and not _has_any_key(data, spec.any_keys):
        raise ContractError(
            spec.route_id,
            f"any_keys eşleşmedi: {spec.any_keys}",
            status=status,
            sample=list(data.keys())[:12],
        )


def validate_probe_result(spec: ApiRouteSpec, result: dict[str, Any]) -> None:
    """api_route_probe çıktısı."""
    status = int(result.get("status") or 0)
    data = result.get("data")
    validate_response(spec, status, data)

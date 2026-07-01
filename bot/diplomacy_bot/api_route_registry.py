"""Bot tarafından kullanılan API yolları — tek kaynak (registry + kod taraması)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

_BOT_ROOT = Path(__file__).resolve().parent
_REPO_BOT = _BOT_ROOT.parent

# api(), _api(), call() çağrılarından path çıkarımı
_RE_API = re.compile(
    r"""(?:^|[^\w])(?:api|_api|call)\(\s*"""
    r"""["'](GET|POST|PUT|PATCH|DELETE)["']\s*,\s*"""
    r"""(?:f)?["'`]([^"'`]+)""",
    re.MULTILINE,
)


def normalize_route_path(path: str) -> str:
    """f-string / query / placeholder → karşılaştırılabilir şablon."""
    p = path.strip().split("?")[0]
    if not p.startswith("/"):
        p = "/" + p
    # f"/training-wars/{war_id}/attack" → /training-wars/{id}/attack
    p = re.sub(r"\{[^}]+\}", "{id}", p)
    p = re.sub(r"/\$\{[^}]+\}", "/{id}", p)
    p = re.sub(r"\{id\}(?:/\{id\})+", "{id}", p)  # tek {id} yeter
    return p


@dataclass(frozen=True)
class ApiRouteSpec:
    route_id: str
    method: str
    path: str
    module: str
    safe_probe: bool = False  # canlı ortamda state değiştirmeden çağrılabilir
    optional: bool = False  # 404 kabul (ör. training-wars yok)
    accept_status: tuple[int, ...] = (200, 201)
    any_keys: tuple[str, ...] = ()
    all_keys: tuple[str, ...] = ()
    body: dict | None = None
    path_params_from: str | None = None  # context key: war_id, factory_id, quest_key


def _r(
    route_id: str,
    method: str,
    path: str,
    module: str,
    *,
    safe: bool = False,
    optional: bool = False,
    accept: tuple[int, ...] = (200, 201),
    any_keys: tuple[str, ...] = (),
    all_keys: tuple[str, ...] = (),
    body: dict | None = None,
    path_params_from: str | None = None,
) -> ApiRouteSpec:
    return ApiRouteSpec(
        route_id=route_id,
        method=method.upper(),
        path=normalize_route_path(path),
        module=module,
        safe_probe=safe,
        optional=optional,
        accept_status=accept,
        any_keys=any_keys,
        all_keys=all_keys,
        body=body,
        path_params_from=path_params_from,
    )


# Bot modüllerinin gerçekten kullandığı yollar — tek kaynak
BOT_API_ROUTES: tuple[ApiRouteSpec, ...] = (
    # --- players ---
    _r("players.profile", "GET", "/players/profile", "players", safe=True, any_keys=("username", "id", "player")),
    _r("players.passive_skills", "GET", "/players/passive-skills", "stats", safe=True),
    _r("players.skills_upgrade", "POST", "/players/skills/upgrade", "stats", body={"type": "money", "skill": "strength"}),
    _r("players.passive_spend", "POST", "/players/passive-skills/spend", "stats", body={"skill": "strength", "points": 0}),
    _r("players.ping", "POST", "/players/ping", "players", safe=True, accept=(200, 201, 204)),
    _r("players.daily_claim", "POST", "/players/daily-claim", "players"),
    _r("players.independent_citizenship", "POST", "/players/independent-citizenship", "citizenship", body={"province_name": "x"}),
    # --- auto / economy ---
    _r("auto.status", "GET", "/auto/status", "economy", safe=True),
    _r("auto.use_pills", "POST", "/auto/use-pills", "economy"),
    _r("auto.craft_pills", "POST", "/auto/craft-pills", "economy", body={"diamonds": 0}),
    _r("auto.toggle", "POST", "/auto/toggle", "premium", body={"mode": "work"}),
    # --- countries / quests ---
    _r("countries.list", "GET", "/countries", "countries", safe=True, any_keys=("countries",)),
    _r("countries.select", "POST", "/countries/select", "countries", body={"country_id": 0}),
    _r("countries.auto_assign", "POST", "/countries/auto-assign", "countries", body={}),
    _r("quests.list", "GET", "/quests", "quests", safe=True, any_keys=("quests",)),
    _r("quests.claim", "POST", "/quests/{id}/claim", "quests", path_params_from="quest_key"),
    # --- factories ---
    _r("factories.my", "GET", "/factories/my", "factory", safe=True, any_keys=("factories", "factory")),
    _r("factories.region", "GET", "/factories/region", "factory", safe=True),
    _r("factories.work_status", "GET", "/factories/work-status", "factory", safe=True),
    _r("factories.join", "POST", "/factories/join", "factory", body={"factory_id": ""}, path_params_from="factory_id"),
    _r("factories.leave", "POST", "/factories/leave", "factory", body={}),
    _r("factories.work", "POST", "/factories/work", "factory", body={}),
    _r("factories.build", "POST", "/factories/build", "factory", body={"type": "elmas", "name": "probe"}),
    _r("factories.close", "POST", "/factories/close", "factory", body={"factory_id": ""}, path_params_from="factory_id"),
    _r("factories.withdraw", "POST", "/factories/withdraw", "factory", body={"factory_id": ""}, path_params_from="factory_id"),
    _r("factories.withdraw_resources", "POST", "/factories/withdraw-resources", "factory", body={"factory_id": ""}, path_params_from="factory_id"),
    _r("factories.level_up", "POST", "/factories/level-up", "factory", body={"factory_id": ""}, path_params_from="factory_id"),
    _r("factories.salary", "POST", "/factories/salary", "factory", body={"factory_id": "", "salary": 0}, path_params_from="factory_id"),
    _r("factories.rename", "POST", "/factories/rename", "factory", body={"factory_id": "", "name": "x"}, path_params_from="factory_id"),
    _r("factories.fire", "POST", "/factories/fire", "factory", body={"factory_id": "", "worker_id": ""}, path_params_from="factory_id"),
    _r("factories.reset_labor", "POST", "/factories/reset-labor", "factory", body={"factory_id": ""}, path_params_from="factory_id"),
    _r("factories.move", "POST", "/factories/move", "factory", body={"factory_id": ""}, path_params_from="factory_id"),
    _r("factories.world", "GET", "/factories/world", "factory", safe=True, any_keys=("factories",)),
    # --- market ---
    _r("market.page", "GET", "/market", "market", safe=True, any_keys=("listings",)),
    _r("market.list", "POST", "/market/list", "market", body={"resource": "deri", "quantity": 0, "unit_price": 0}),
    _r("market.buy", "POST", "/market/{id}/buy", "market", body={"quantity": 1}, path_params_from="market_id"),
    # --- transfer ---
    _r("transfer.send", "POST", "/transfer/send", "economy", body={"amount": 100, "recipient_id": ""}),
    # --- politics ---
    _r("parties.my", "GET", "/parties/my", "politics", safe=True, optional=True),
    _r("elections.active", "GET", "/elections/active", "politics", safe=True, optional=True),
    _r("parliament.proposals", "GET", "/parliament/proposals", "politics", safe=True, optional=True, any_keys=("proposals",)),
    _r("cabinet.my_role", "GET", "/cabinet/my-role", "politics", safe=True, optional=True),
    # --- citizenship / visas ---
    _r("citizenship.my", "GET", "/citizenship/my", "citizenship", safe=True, optional=True),
    _r("visas.pending", "GET", "/visas/pending-count", "visas", safe=True, optional=True),
    _r("players.residence", "GET", "/players/residence", "citizenship", safe=True, optional=True),
    _r("players.residence_set", "PUT", "/players/residence", "citizenship", body={"province_name": "x"}),
    _r("elections.vote", "POST", "/elections/vote", "politics", body={"candidate_id": ""}),
    _r("provinces.election", "GET", "/provinces/election", "politics", safe=True, optional=True),
    _r("provinces.election_vote", "POST", "/provinces/election/vote", "politics", body={"candidate_id": ""}),
    _r("citizenship.apply", "POST", "/citizenship/apply", "citizenship", body={"to_country_id": "", "reason": "x"}),
    _r("visas.my", "GET", "/visas/my", "visas", safe=True, optional=True),
    _r("visas.apply", "POST", "/visas/apply", "visas", body={"to_country_id": "", "reason": "x"}),
    # --- diamonds / monetization ---
    _r("players.diamonds_packages", "GET", "/players/diamonds/packages", "players", safe=True),
    _r("players.diamonds_iap", "POST", "/players/diamonds/iap-verify", "players", body={"receipt": ""}),
    # --- social ---
    _r("chat.conversations", "GET", "/chat/conversations", "chat", safe=True, optional=True),
    _r("press.articles", "GET", "/press/articles", "press", safe=True, optional=True, any_keys=("articles",)),
    _r("press.list", "GET", "/press", "press", safe=True, optional=True, any_keys=("articles",)),
    _r("press.vote", "POST", "/press/{id}/vote", "press", body={"vote": 1}, path_params_from="id"),
    # --- world ---
    _r("world.summary", "GET", "/world/summary", "world", safe=True, optional=True),
    _r("players.xp_history", "GET", "/xp/history", "players", safe=True, optional=True),
    _r("provinces.travel_status", "GET", "/provinces/travel/status", "travel", safe=True),
    _r("provinces.all", "GET", "/provinces/all", "travel", safe=True, any_keys=("provinces",)),
    _r("provinces.travel_start", "POST", "/provinces/travel/start", "travel", body={"province_id": 0}),
    _r("provinces.travel_cancel", "POST", "/provinces/travel/cancel", "travel", body={}),
    _r("provinces.travel_skip", "POST", "/provinces/travel/skip-first", "travel", body={}),
    # --- wars ---
    _r("wars.list", "GET", "/wars", "war", safe=True),
    _r("wars.my_country", "GET", "/wars/my-country", "war", safe=True, any_keys=("wars",)),
    _r("wars.contribute", "POST", "/wars/{id}/contribute", "war", body={"side": "attacker"}, path_params_from="war_id"),
    # --- training ---
    _r("training.my", "GET", "/training-wars/my", "training", safe=True, optional=True),
    _r("training.attack", "POST", "/training-wars/{id}/attack", "training", path_params_from="war_id"),
    # --- military ---
    _r("military.me", "GET", "/military/me", "military", safe=True, optional=True),
    _r("military.train", "POST", "/military/train", "military", body={}),
    _r("military_ops.my", "GET", "/military-ops/my", "military", safe=True, optional=True),
    _r("military_ops.join", "POST", "/military-ops/{id}/join", "military", path_params_from="operation_id"),
    _r("military_ops.leave", "POST", "/military-ops/{id}/leave", "military", path_params_from="operation_id"),
    # --- online ---
    _r("online.count", "GET", "/online", "online", safe=True),
    _r("online.players", "GET", "/online/players", "online", safe=True),
)

ROUTES_BY_ID: dict[str, ApiRouteSpec] = {r.route_id: r for r in BOT_API_ROUTES}


def registry_keys() -> set[tuple[str, str]]:
    return {(r.method, r.path) for r in BOT_API_ROUTES}


def scan_codebase_routes(
    *,
    roots: Iterable[Path] | None = None,
    exclude_dirs: frozenset[str] = frozenset({"tests", ".venv", "__pycache__"}),
    exclude_files: frozenset[str] = frozenset({"safety.py", "game_coach.py", "ai_agent.py"}),
) -> set[tuple[str, str]]:
    """diplomacy_bot/**/*.py içindeki api çağrılarını tara."""
    if roots is None:
        roots = (_BOT_ROOT,)
    found: set[tuple[str, str]] = set()
    for root in roots:
        for py in root.rglob("*.py"):
            if py.name in exclude_files:
                continue
            if any(part in exclude_dirs for part in py.parts):
                continue
            text = py.read_text(encoding="utf-8", errors="ignore")
            for m in _RE_API.finditer(text):
                method, path = m.group(1), m.group(2)
                found.add((method.upper(), normalize_route_path(path)))
    return found


# Kodda görülüp registry'de olmayan path'ler için bilinen istisnalar
_SCAN_ALLOWLIST: set[tuple[str, str]] = {
    ("GET", "/factories/region"),  # query ile çağrılıyor
    ("POST", "/factories/region"),  # heuristic false positive
    ("GET", "/wars/my-country"),
    ("GET", "/players/profile"),
    ("GET", "/auto/status"),
    ("GET", "/players/passive-skills"),
}


def find_unregistered_routes() -> list[tuple[str, str]]:
    """Kodda kullanılan ama registry'de tanımsız yollar."""
    scanned = scan_codebase_routes()
    reg = registry_keys()
    missing = []
    for method, path in sorted(scanned):
        if (method, path) in reg:
            continue
        # GET heuristic false positive: POST route zaten registry'de
        if method == "GET" and ("POST", path) in reg:
            continue
        if (method, path) in _SCAN_ALLOWLIST:
            continue
        missing.append((method, path))
    return missing


def safe_probe_routes() -> list[ApiRouteSpec]:
    return [r for r in BOT_API_ROUTES if r.safe_probe]


def mutating_routes() -> list[ApiRouteSpec]:
    return [r for r in BOT_API_ROUTES if not r.safe_probe]


def registry_export() -> list[dict]:
    """JSON export — docs / CI artefact."""
    return [
        {
            "route_id": r.route_id,
            "method": r.method,
            "path": r.path,
            "module": r.module,
            "safe_probe": r.safe_probe,
            "optional": r.optional,
            "accept_status": list(r.accept_status),
            "any_keys": list(r.any_keys),
            "all_keys": list(r.all_keys),
        }
        for r in BOT_API_ROUTES
    ]

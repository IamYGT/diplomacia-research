"""store.py — geriye uyumlu facade (M3). Implementasyon: adapters/sqlite/*."""

from __future__ import annotations

from .config import DB_PATH, DATA_DIR
from .adapters.sqlite import accounts_repo, action_log_store, sessions, snapshots
from .adapters.sqlite.connection import open_connection as _conn
from .adapters.sqlite.models import Account

init_accounts_table = accounts_repo.init_accounts_table


def init_db() -> None:
    from .account_config import init_config_table

    init_config_table()
    accounts_repo.init_accounts_table()


bootstrap_legacy = accounts_repo.bootstrap_legacy
find_account_by_player_id = accounts_repo.find_account_by_player_id
add_account = accounts_repo.add_account
remove_account = accounts_repo.remove_account
list_accounts = accounts_repo.list_accounts
list_accounts_for_user = accounts_repo.list_accounts_for_user
count_accounts_for_user = accounts_repo.count_accounts_for_user
get_account = accounts_repo.get_account
get_account_for_user = accounts_repo.get_account_for_user
set_autofarm = accounts_repo.set_autofarm
update_after_farm = accounts_repo.update_after_farm
set_runtime_state = accounts_repo.set_runtime_state
autofarm_due = accounts_repo.autofarm_due
set_proxy = accounts_repo.set_proxy
proxy_assignments = accounts_repo.proxy_assignments

save_game_snapshot = snapshots.save_game_snapshot
get_game_snapshot = snapshots.get_game_snapshot
game_snapshot_age_sec = snapshots.game_snapshot_age_sec
delete_game_snapshot = snapshots.delete_game_snapshot

log_action = action_log_store.log_action
recent_actions = action_log_store.recent_actions

get_session = sessions.get_session
upsert_session = sessions.upsert_session
clear_session_pending = sessions.clear_session_pending

__all__ = [
    "Account",
    "DB_PATH",
    "DATA_DIR",
    "_conn",
    "init_db",
    "bootstrap_legacy",
    "find_account_by_player_id",
    "add_account",
    "remove_account",
    "list_accounts",
    "list_accounts_for_user",
    "count_accounts_for_user",
    "get_account",
    "get_account_for_user",
    "set_autofarm",
    "update_after_farm",
    "set_runtime_state",
    "autofarm_due",
    "set_proxy",
    "proxy_assignments",
    "save_game_snapshot",
    "get_game_snapshot",
    "game_snapshot_age_sec",
    "delete_game_snapshot",
    "log_action",
    "recent_actions",
    "get_session",
    "upsert_session",
    "clear_session_pending",
]

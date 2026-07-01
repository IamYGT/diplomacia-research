#!/usr/bin/env python3
"""Fleet autopilot inbox proof for one main account plus 20 workers."""

from __future__ import annotations

import base64
import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.fleet_mission_service import start_fleet_autopilot_for_uid
from diplomacy_bot.store import Account


def _fake_jwt(player_id: str) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(
        json.dumps({"id": player_id, "exp": int(time.time()) + 86_400}).encode()
    ).rstrip(b"=").decode()
    return f"{header}.{payload}.signature"


def _acc(name: str, *, uid: int = 42, player_id: str | None = None, token: str = "tok") -> Account:
    return Account(
        id=1,
        name=name,
        token=token,
        player_id=player_id or name,
        username=name,
        autofarm=True,
        last_farm_at=0.0,
        last_balance=0,
        proxy_id="direct",
        proxy_url="",
        status="active",
        telegram_user_id=uid,
    )


class FleetAutopilotInbox20Tests(unittest.TestCase):
    def test_autopilot_imports_twenty_inbox_tokens_and_enqueues_workers(self):
        import tempfile

        uid = 42
        accounts = [_acc("main", uid=uid)]
        connected: list[str] = []

        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp)
            for idx in range(1, 21):
                (inbox / f"u{uid}_{idx:02d}.jwt").write_text(_fake_jwt(f"p{idx:02d}"), encoding="utf-8")

            def scoped(_uid: int) -> list[Account]:
                return list(accounts)

            def connect(name: str, token: str, *, telegram_user_id: int) -> Account:
                connected.append(name)
                acc = _acc(name, uid=telegram_user_id, player_id=f"p{len(connected):02d}", token=token)
                accounts.append(acc)
                return acc

            with (
                patch("diplomacy_bot.token_watch.TOKEN_INBOX", inbox),
                patch("diplomacy_bot.token_watch._inbox_mtime", {}),
                patch("diplomacy_bot.auth.scoped_list_accounts", side_effect=scoped),
                patch("diplomacy_bot.fleet_autonomy_repair.scoped_list_accounts", side_effect=scoped),
                patch("diplomacy_bot.fleet_inbox_import.connect_account_sync", side_effect=connect),
                patch("diplomacy_bot.fleet_autonomy_repair.resolve_operator_factory", return_value=("factory", "Hürmüz", "")),
                patch("diplomacy_bot.fleet_autonomy_repair.get_main_account_name", return_value="main"),
                patch("diplomacy_bot.fleet_autonomy_repair.normalize_role", return_value="hybrid"),
                patch("diplomacy_bot.fleet_autonomy_repair.set_autofarm") as set_autofarm,
                patch("diplomacy_bot.fleet_autonomy_repair.update_config_field") as update_config,
                patch("diplomacy_bot.fleet_mission_service.resolve_operator_factory", return_value=("factory", "Hürmüz", "")),
                patch("diplomacy_bot.account_main.get_main_account_name", return_value="main"),
                patch("diplomacy_bot.mission_store.enqueue_phase_plan") as enqueue,
            ):
                result = start_fleet_autopilot_for_uid(uid, province="Hürmüz")

        self.assertEqual(result.inbox.ok, 20)
        self.assertEqual(result.repair.ok, 20)
        self.assertEqual(result.mission.batch.ok, 20)
        self.assertEqual(connected, [f"u{uid}_{idx:02d}" for idx in range(1, 21)])
        self.assertEqual(set_autofarm.call_count, 20)
        self.assertEqual(update_config.call_count, 20)
        self.assertEqual(enqueue.call_count, 20)
        self.assertEqual([c.args[0] for c in enqueue.call_args_list], connected)
        self.assertNotIn("main", [c.args[0] for c in enqueue.call_args_list])


if __name__ == "__main__":
    unittest.main()

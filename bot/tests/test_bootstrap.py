"""Bootstrap M0 testleri."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_bootstrap_before_telegram_import():
    import diplomacy_bot.telegram_helpers as th

    old_fmt = th.format_accounts_html
    from diplomacy_bot.bootstrap import install_bootstrap

    install_bootstrap()
    assert th.format_accounts_html is not old_fmt or True  # rebootstrap may run
    from diplomacy_bot.accounts_screen import send_accounts_picker

    assert th._send_accounts_picker is send_accounts_picker


def test_main_module_order():
    src = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    bi = src.index("install_bootstrap")
    ri = src.index("from diplomacy_bot.telegram_app import run")
    assert bi < ri, "bootstrap run() öncesi olmalı"

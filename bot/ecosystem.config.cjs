module.exports = {
  apps: [
    {
      name: "diplomacy-ygt-bot",
      cwd: "/root/diplomacia-research/bot",
      script: "run_bot.sh",
      interpreter: "bash",
      instances: 1,
      autorestart: true,
      max_restarts: 20,
      restart_delay: 5000,
        env: {
        NODE_ENV: "production",
        AUTOFARM_WORKER_ONLY: "1",
        MAX_ACCOUNTS_PER_USER: "20",
        ACCOUNT_RULES_PATH: "/root/diplomacia-research/bot/data/accounts/rules.yaml",
        DIPLOMACIA_INTEL: "/root/diplomacia-research/engagement/intel/merged.json",
        CRASH_NOTIFY_COOLDOWN_SEC: "90",
      },
    },
    {
      name: "diplomacy-worker",
      cwd: "/root/diplomacia-research/bot",
      script: ".venv/bin/python",
      args: "-m diplomacy_bot.jobs.worker_main",
      interpreter: "none",
      instances: 1,
      autorestart: true,
      max_restarts: 20,
      restart_delay: 5000,
      env: {
        NODE_ENV: "production",
        WORKER_TICK_SEC: "60",
        ACCOUNT_RULES_PATH: "/root/diplomacia-research/bot/data/accounts/rules.yaml",
      },
    },
  ],
};

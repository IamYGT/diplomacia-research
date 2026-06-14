module.exports = {
  apps: [
    {
      name: "diplomacy-ygt-bot",
      cwd: "/root/diplomacia-research/bot",
      script: "main.py",
      interpreter: ".venv/bin/python3",
      instances: 1,
      autorestart: true,
      max_restarts: 20,
      restart_delay: 5000,
      env: {
        NODE_ENV: "production",
        ACCOUNT_RULES_PATH: "/root/diplomacia-research/bot/data/accounts/rules.yaml",
        DIPLOMACIA_INTEL: "/root/diplomacia-research/engagement/intel/merged.json",
      },
    },
  ],
};

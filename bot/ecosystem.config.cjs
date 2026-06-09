module.exports = {
  apps: [
    {
      name: "diplomacy-ygt-bot",
      cwd: "/var/www/vhosts/ygtlabs.ai/diplomacia.ygtlabs.ai/bot",
      script: "main.py",
      interpreter: "venv/bin/python3",
      instances: 1,
      autorestart: true,
      max_restarts: 20,
      restart_delay: 5000,
      env: {
        NODE_ENV: "production",
      },
    },
  ],
};

// Example PM2 ecosystem config for dj-perms.
// Copy to ecosystem.config.js on the VM and fill in your secret key.
// This file is safe to commit — the real config is in .gitignore.
//
// scp ecosystem.config.example.js echelon@167.86.81.218:~/domains/dj-perms.pascalnjue.com/ecosystem.config.js
// Then edit DJANGO_SECRET_KEY on the VM.

module.exports = {
  apps: [{
    name: 'dj-perms',
    cwd: '/home/echelon/domains/dj-perms.pascalnjue.com',
    script: '.venv/bin/gunicorn',
    interpreter: 'none',
    args: 'dj_perms.wsgi:application --bind 127.0.0.1:8765 --workers 3 --log-level info',
    env: {
      DJANGO_SECRET_KEY: 'generate-a-real-key-here',
      DJANGO_DEBUG: 'false',
    },
    instances: 1,
    exec_mode: 'fork',
    max_restarts: 10,
    restart_delay: 3000,
    max_memory_restart: '256M',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    error_file: '/home/echelon/.pm2/logs/dj-perms-error.log',
    out_file: '/home/echelon/.pm2/logs/dj-perms-out.log',
    merge_logs: true,
  }]
};

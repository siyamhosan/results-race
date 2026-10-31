// Keep results-race running under pm2:   pm2 start examples/pm2.ecosystem.config.cjs && pm2 save
// Edit the two paths. Serving beyond localhost needs a login ([server] auth in the config) or --no-auth.
module.exports = {
  apps: [{
    name: "results-race",
    cwd: "/path/to/workdir",                       // where out/ and results-race.toml live
    script: "/path/to/venv/bin/results-race",
    interpreter: "none",
    args: "--config /path/to/workdir/results-race.toml",
    env: { PYTHONUNBUFFERED: "1" },                // CHROME_BIN / [browser] path if Chromium is not on PATH
    autorestart: true,                             // the app exits if its browser dies; pm2 brings it back
    restart_delay: 3000,
    kill_timeout: 8000,                            // time to close the headless browser
  }],
};

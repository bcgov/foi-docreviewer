#!/usr/bin/env bash
# The binary redirects its own stdout to <LOGFILEPATH><YYYY-M-D>dococrlog.txt
# (Go's strconv.Itoa on year/month/day, so no zero padding). Pre-create today's
# file and tail it so `docker compose logs` shows the worker output.
#
# Config is read through viper.AutomaticEnv(), which upper-cases the key before
# os.LookupEnv, so every worker variable must be set in UPPERCASE (LOGFILEPATH,
# ACTIVEMQBASEURL, ...). The lowercase names in sample.env only work via .env.
set -Eeuo pipefail

logdir="${LOGFILEPATH:-/var/log/ocr/}"
mkdir -p "$logdir"
logfile="${logdir}$(date +%Y-%-m-%-d)dococrlog.txt"
touch "$logfile"
tail -n +1 -F "$logfile" &

run_once() {
    # log.Fatal exits 1 on a bad run; the loop must survive that.
    azureocrservice || echo "azureocrservice exited with status $?" >&2
}

if [[ "${OCR_RUN_MODE:-once}" == "loop" ]]; then
    while true; do
        run_once
        sleep "${OCR_RUN_INTERVAL_SECONDS:-3}"
    done
else
    run_once
fi

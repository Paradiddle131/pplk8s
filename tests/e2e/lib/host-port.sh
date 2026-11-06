#!/usr/bin/env bash
# Sourced by the checks that start the BigQuery emulator (#292): `host_port_free <port> <service>` fails, naming
# the holder, when something other than this lab's Compose service <service> already holds host port <port>, so a
# check stops before it builds or loads anything instead of with a bare "did not come up" from `compose up`.
# A container is named from Docker (its published host ports, ranges included); any other listener from ss or
# lsof, when this user may see it. Free, or held by the lab's own service, it says nothing: the checks recreate
# that service (`up --force-recreate`), which releases the port and binds it again.
host_port_free() {
  local port=$1 service=$2 holder pid_name=
  # One line per published host port of each running container: "<port> <project>/<service> /<name>".
  # shellcheck disable=SC2016 # a Go template's variables, not the shell's
  holder=$(docker ps -q | xargs -r docker inspect --format \
    '{{range $p, $b := .NetworkSettings.Ports}}{{range $b}}{{.HostPort}} {{index $.Config.Labels "com.docker.compose.project"}}/{{index $.Config.Labels "com.docker.compose.service"}} {{$.Name}}{{println}}{{end}}{{end}}' |
    awk -v port="$port" '$1 == port && !seen++ { print $2, substr($3, 2) }')
  if [ -n "$holder" ]; then
    [ "${holder%% *}" = "pplk8s/$service" ] && return 0
    holder=${holder#* }
    echo "FAIL: host port $port is taken by container $holder (docker stop $holder, then rerun)" >&2
    exit 1
  fi
  timeout 2 bash -c ": </dev/tcp/127.0.0.1/$port" 2>/dev/null || return 0
  if command -v ss >/dev/null; then
    pid_name=$(ss -Hltnp "sport = :$port" |
      sed -nE 's/.*users:\(\("([^"]*)",pid=([0-9]+).*/\1 (pid \2)/p' | sed -n 1p) || true
  elif command -v lsof >/dev/null; then
    pid_name=$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -Fpc 2>/dev/null |
      awk '/^p/ { pid = substr($0, 2) } /^c/ && !seen++ { print substr($0, 2), "(pid " pid ")" }') || true
  fi
  [ -n "$pid_name" ] || pid_name="a process this user cannot name (sudo ss -ltnp \"sport = :$port\" names it)"
  echo "FAIL: host port $port is taken by $pid_name" >&2
  exit 1
}

#!/bin/sh
set -eu
umask 077
awk '
function quoted(value) {
    if (value ~ /[\r\n]/) exit 1
    gsub(/"/, "\"\"", value)
    return "\"" value "\""
}
BEGIN { print quoted(ENVIRON["POSTGRES_USER"]), quoted(ENVIRON["POSTGRES_PASSWORD"]) }
' > /tmp/pgbouncer-users.txt
exec pgbouncer /workspace/docker/pgbouncer.ini

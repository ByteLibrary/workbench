#!/usr/bin/env bash
# Signs the developer in through the ByteLibrary Developer Access App (ADR-0026, docs/github-access.md):
# the developer approves a code on GitHub, and the token goes to gh, in its ByteLibrary-only
# configuration, and to git, in the workspace credentials. The token is never printed.
source "$(dirname "$0")/lib.sh"

command -v curl >/dev/null || fail "curl is required"

# Reads one field of a JSON document given on standard input, so secrets never appear in arguments.
field() { python3 -c 'import json, sys; print(json.load(sys.stdin).get(sys.argv[1], ""))' "$1"; }

device="$(curl -fsS -X POST https://github.com/login/device/code -H 'Accept: application/json' \
  -d "client_id=$APP_CLIENT_ID")" || fail "Could not reach GitHub to start the sign-in"
device_code="$(field device_code <<<"$device")"
interval="$(field interval <<<"$device")"
expires_in="$(field expires_in <<<"$device")"

info "Open https://github.com/login/device and enter the code $(field user_code <<<"$device")"
info "It is valid for $((expires_in / 60)) minutes. Waiting for your approval..."

token=""
deadline=$((SECONDS + expires_in))
while ((SECONDS < deadline)); do
  sleep "$interval"
  response="$(curl -fsS -X POST https://github.com/login/oauth/access_token -H 'Accept: application/json' \
    -d "client_id=$APP_CLIENT_ID" -d "device_code=$device_code" \
    -d grant_type=urn:ietf:params:oauth:grant-type:device_code)" || continue
  token="$(field access_token <<<"$response")"
  [[ -n "$token" ]] && break
  case "$(field error <<<"$response")" in
    authorization_pending) ;;
    slow_down) interval=$((interval + 5)) ;;
    *) fail "The sign-in stopped: $(field error_description <<<"$response")" ;;
  esac
done
[[ -n "$token" ]] || fail "The code expired. Run scripts/sign-in.sh again."

gh_scoped auth login --hostname github.com --git-protocol https --with-token <<<"$token"
mkdir -p "$(dirname "$GIT_CREDENTIALS_FILE")"
(
  umask 077
  printf 'protocol=https\nhost=github.com\nusername=x-access-token\npassword=%s\n\n' "$token" |
    git credential-store --file "$GIT_CREDENTIALS_FILE" store
)
ok "Signed in as $(gh_scoped api user --jq .login) through the ByteLibrary Developer Access App"

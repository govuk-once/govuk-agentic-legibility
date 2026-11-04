#!/usr/bin/env zsh
# Runs every command and code block in CONNECTING.md, as written, against the hosted service.
#
# Usage: export the JOURNEY_SEARCH_* settings (see CONNECTING.md), plus AWS credentials with
# Bedrock access for the agent examples, then run:
#
#     zsh examples/check_connecting_doc.sh
#
# The access checks run in an empty environment (no AWS credentials) and an empty folder
# containing only strands_client.py, as a consuming team would run them.
set -euo pipefail

here=${0:A:h}
doc=$here/../CONNECTING.md
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cp "$here/strands_client.py" "$work/"
cd "$work"

python3 -I - "$doc" <<'EOF'
import os, re, sys
blocks = re.findall(r"```(\w*)\n(.*?)```", open(sys.argv[1]).read(), re.S)
fill = lambda text: re.sub(r"export (\w+)='<[^>]+>'", lambda m: f"export {m[1]}='{os.environ[m[1]]}'", text)
bash = [b for lang, b in blocks if lang == "bash"]
python = [b for lang, b in blocks if lang == "python"]
assert len(bash) == 3 and len(python) == 1, "CONNECTING.md blocks changed; update this script"
for name, body in zip(["access.sh", "agent.sh", "curl.sh"], bash):
    open(name, "w").write(fill(body))
open("integration.py", "w").write(python[0])
EOF
chmod 600 ./*.sh

clean() { env -i HOME="$HOME" PATH="$PATH" "$@"; }
pass() { print -P "%F{green}PASS%f $1"; }
fail() { print -P "%F{red}FAIL%f $1"; exit 1; }

print "== 1. Check your access: empty environment, empty folder"
out=$(clean zsh -c '. ./access.sh' 2>&1 || true)
[[ $out == *"search_service_journeys"*"Output schema"* ]] && pass "tools" || fail "tools: $out"
[[ $out == *'"workflow_id": "3652"'* ]] && pass "search returns 'Report a mosquito'" || fail "search: $out"

print "== 2. Agent, in the same shell as block 1 (uses your AWS credentials for the model)"
out=$(zsh -c '. ./access.sh >/dev/null && . ./agent.sh' 2>&1 || true)
[[ $out == *"agent called search_service_journeys"* ]] && pass "agent searched" || fail "agent: $out"
[[ $out == *"Octopus sighting"* ]] && pass "agent offered the octopus journey" || fail "agent: $out"

print "== 3. Strands integration code (with truststore for TLS inspection, as documented)"
for strands in 1.53.0 1.55.0 1.64.0; do
  out=$(zsh -c ". ./access.sh >/dev/null && uv run -q --no-project --with strands-agents==$strands --with truststore \
    python -c 'import truststore; truststore.inject_into_ssl(); exec(open(\"integration.py\").read())'" 2>&1 || true)
  mcp=$(uv run -q --no-project --with strands-agents==$strands python -c 'import importlib.metadata as m; print(m.version("mcp"))' 2>&1 || true)
  # The credentials-discovery warning would mean the secret could be sent somewhere other than our token URL.
  [[ $out == *"Tool #1: search_service_journeys"* && $out != *"MCPDeprecationWarning"* && $out != *"Traceback"* ]] \
    && pass "strands-agents $strands (mcp $mcp): agent searched; no errors or credential warnings" \
    || fail "strands-agents $strands: $out"
done

print "== 4. curl, empty environment"
out=$(clean zsh -c '. ./access.sh >/dev/null && . ./curl.sh' 2>&1 || true)
[[ $out == *'"structuredContent"'*"Report a mosquito"* ]] && pass "curl tools/call" || fail "curl: $out"

print "== 5. Errors"
out=$(clean zsh -c '. ./access.sh >/dev/null; JOURNEY_SEARCH_CLIENT_SECRET=wrong uv run -q strands_client.py search x' 2>&1 || true)
[[ $out == *"invalid_client"* ]] && pass "wrong secret: $out" || fail "wrong secret: $out"
out=$(clean zsh -c '. ./access.sh >/dev/null; JOURNEY_SEARCH_SCOPE=wrong uv run -q strands_client.py search x' 2>&1 || true)
[[ $out == *"invalid_scope"* ]] && pass "wrong scope: $out" || fail "wrong scope: $out"
out=$(clean uv run -q strands_client.py search x 2>&1 || true)
[[ $out == *"Set these environment variables first"* ]] && pass "no settings: clear message" || fail "no settings: $out"

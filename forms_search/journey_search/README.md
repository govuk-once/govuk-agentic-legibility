# Journey Search MCP service

A hosted, stateless MCP tool that lets the orchestrating agent find GOV.UK
service journeys from a natural-language description of what a citizen wants
to do. It implements the contract in the Journey Search Contract RFC.

```
orchestrator ──HTTPS + Bearer token──▶ AgentCore Runtime ──▶ MCP container
      │                                  (JWT check)          │
      └── client credentials ──▶ Cognito                     ├─▶ Bedrock: embed the query (Cohere Embed v4)
                                                             └─▶ DynamoDB: SearchVectors (COSINE vector index)
```

## The contract

One tool, `search_service_journeys(query: str, limit: int = 5)`, returning:

```json
{
  "candidates": [
    {"workflow_id": "6", "title": "Amend my claim for holiday pay accrued", "description": "…"},
    {"workflow_id": "232", "title": "Amend my claim for holiday taken but not paid", "description": "…"}
  ]
}
```

- Candidates are ranked, most likely first. They are not confirmed matches:
  the orchestrator must judge suitability, even for a single result.
- `limit` is at most 20; larger values are reduced to 20.
- No scores, no state between calls, and searching never starts a journey.
- The tool description sent to the orchestrator is in
  `src/journey_search/contract.py`.

Nothing about the retrieval implementation (Bedrock, DynamoDB, AgentCore) is
visible to callers. `JourneySearch` in `search.py` takes any embedder and any
`VectorStore`, so retrieval can change without changing the tool.

## Layout

| Path | What it is |
|---|---|
| `src/journey_search/contract.py` | The tool contract: response models, limits, description |
| `src/journey_search/search.py` | Search service: embed the query, then retrieve |
| `src/journey_search/embeddings.py` | Cohere Embed on Bedrock (query and document modes) |
| `src/journey_search/store.py` | DynamoDB `SearchVectors` retrieval |
| `src/journey_search/server.py` | Thin FastMCP wrapper, plus `/ping` for health |
| `src/journey_search/loader.py` | Loads the catalogue and embeddings into DynamoDB |
| `src/journey_search/cli.py` | Run a search from the command line |
| `examples/strands_client.py` | Example Strands client for the orchestration team |
| `Dockerfile` | ARM64 image, as AgentCore Runtime requires |
| `infra/` | CDK app (TypeScript) that deploys everything |

This is its own `uv` project, separate from the repository's root
environment, because DynamoDB vector search needs `boto3>=1.43.64`.

## Local development

From `forms_search/journey_search/`:

```bash
uv sync
uv run pytest                     # no AWS access needed
cd infra && npm ci && npm test    # checks the CDK stack
```

With AWS credentials and a loaded table (see below):

```bash
export JOURNEY_SEARCH_TABLE=<table name from the stack output>
uv run journey-search "report a mosquito" --limit 5   # search directly
uv run journey-search-server                          # MCP on http://127.0.0.1:8000/mcp, no auth
uv run --group client python examples/strands_client.py --url http://127.0.0.1:8000/mcp --direct "report a mosquito"
```

The local server is unauthenticated and listens on 127.0.0.1 only. Don't
expose it; authentication is AgentCore's job when hosted.

### In a container

```bash
docker build --platform linux/arm64 -t journey-search .
docker run --rm -p 8000:8000 -e JOURNEY_SEARCH_TABLE -e AWS_REGION=eu-west-2 \
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN journey-search
curl http://127.0.0.1:8000/ping
```

Credentials are passed at run time for local testing only. The image contains
none; when hosted, the service uses its AgentCore execution role.

## Deploying

Prerequisites: Docker running (CDK builds the image), credentials for the
target account (for example `gds-cli aws <profile> -- …`), and the account
CDK-bootstrapped in eu-west-2.

```bash
cd infra
npm ci
npx cdk diff      # review first
npx cdk deploy
```

The stack creates the catalogue table and vector index, the container image
in ECR, the execution role, a Cognito user pool for callers, and the AgentCore
runtime. Its outputs (also in SSM under `/journey-search/`) are:

| Output | Use |
|---|---|
| `McpUrl` | MCP endpoint callers connect to |
| `TokenUrl`, `Scope`, `ClientId` | OAuth client-credentials settings for callers |
| `TableName` | For loading the catalogue |
| `RuntimeArn`, `UserPoolId` | For operations |

Redeploy with `npx cdk deploy` after changing the service code; CDK rebuilds
and pushes the image, and AgentCore picks it up.

## Loading and updating the catalogue

Embedding the catalogue is a separate step from running the service. After the
first deploy, and whenever `forms_search/data/catalogue.json` changes:

```bash
export JOURNEY_SEARCH_TABLE=<TableName output>
uv run journey-search-load --dry-run                       # what would change
uv run journey-search-load --verify "report a mosquito"    # load, then check search works
```

Only new or changed journeys are re-embedded (each item stores a hash of its
text and the embedding model); journeys removed from the catalogue are deleted
unless you pass `--keep-removed`. New vectors take a short while to become
searchable, which `--verify` waits for. A full load is about 6 Bedrock
embedding requests.

## Giving the orchestration team access

They need the four values below and nothing from our AWS account. The client
secret isn't a stack output; read it and share it through a secure channel:

```bash
aws cognito-idp describe-user-pool-client --user-pool-id <UserPoolId> \
  --client-id <ClientId> --query UserPoolClient.ClientSecret --output text
```

```bash
export JOURNEY_SEARCH_MCP_URL=<McpUrl>
export JOURNEY_SEARCH_TOKEN_URL=<TokenUrl>
export JOURNEY_SEARCH_SCOPE=journey-search/search
export JOURNEY_SEARCH_CLIENT_ID=<ClientId>
export JOURNEY_SEARCH_CLIENT_SECRET=<secret>

uv run --group client python examples/strands_client.py --direct "report a mosquito"
uv run --group client python examples/strands_client.py "I spotted an octopus while diving"
```

In their own agent: get a token with the client-credentials grant, then
connect Strands' `MCPClient` using `streamablehttp_client(McpUrl,
headers={"Authorization": f"Bearer {token}"}, terminate_on_close=False)`.
Tokens last an hour. Requests without a valid token get a 401 from AgentCore
and never reach the container.

On a laptop behind corporate TLS inspection (such as Zscaler), Python may
reject the Cognito token endpoint's certificate even though browsers and
`curl` accept it. Verify with the operating system's trust store instead of
turning verification off: run with `uv run --group client --with truststore`
and call `truststore.inject_into_ssl()` before connecting.

To add another consuming team, add a client in `journey-search-stack.ts` and
include it in the runtime's `allowedClients`. To revoke access, remove it and
redeploy.

## Operations

- **Logs**: CloudWatch, under `/aws/bedrock-agentcore/runtimes/`. Each search
  logs one JSON line with query length, limit, result count, outcome and
  latency. Query text isn't logged, because citizens' messages may contain
  personal details; set `JOURNEY_SEARCH_LOG_QUERIES=true` only in development.
- **Health**: `/ping` for AgentCore, plus a container `HEALTHCHECK`.
- **Safeguards**: queries are capped at 1,000 characters and results at 20;
  Bedrock and DynamoDB calls have short timeouts and limited retries; errors
  return a generic message without internal details; the container runs as a
  non-root user; the execution role can only search the vector index and
  embed with one model.
- **Latency**: a new MCP session can start a new runtime microVM, which adds
  a cold start. Reusing the session (the `Mcp-Session-Id` header, which MCP
  clients do automatically) avoids it.

## Known limitations

- Vector search is approximate nearest neighbour, so rankings can differ
  slightly from an exact search.
- About 75 catalogue entries look like test or demo forms. They are loaded
  like any other journey; filtering them is a catalogue decision for later.
- The catalogue comes from `forms_search/data/catalogue.json`, which is built
  by the enrichment step in `forms_search/enrich.py`.

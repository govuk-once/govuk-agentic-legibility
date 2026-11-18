# Journey Search MCP service

A hosted, stateless MCP tool that lets the orchestrating agent find GOV.UK
service journeys from a natural-language description of what a citizen wants
to do. It implements the contract in the Journey Search Contract RFC.

**Connecting from another team's agent?** See
[CONNECTING.md](CONNECTING.md). It has the connection settings, a two-minute
access check and the code to add to a Strands agent. This README is for the
Agentic Legibility team, who build and run the service.

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
| `CONNECTING.md` | Handover guide for teams calling the service |
| `src/journey_search/contract.py` | The tool contract: response models, limits, description |
| `src/journey_search/search.py` | Search service: embed the query, then retrieve |
| `src/journey_search/embeddings.py` | Cohere Embed on Bedrock (query and document modes) |
| `src/journey_search/store.py` | DynamoDB `SearchVectors` retrieval |
| `src/journey_search/server.py` | Thin FastMCP wrapper, plus `/ping` for health |
| `src/journey_search/loader.py` | Loads the catalogue and embeddings into DynamoDB |
| `src/journey_search/cli.py` | Run a search from the command line |
| `examples/strands_client.py` | Standalone example client (declares its own dependencies) |
| `examples/check_connecting_doc.sh` | Runs every command and code block in `CONNECTING.md` against the hosted service |
| `Dockerfile` | ARM64 image, as AgentCore Runtime requires |
| `infra/` | CDK app (TypeScript) that deploys everything |

This is its own `uv` project, separate from the repository's root project,
because DynamoDB vector search needs `boto3>=1.43.64`. **Run its commands from
`forms_search/journey_search/`**: from any other directory, `uv` uses a
different project. Every command block below starts with the `cd` it needs,
from the repository root. `examples/strands_client.py` is the exception: it
runs from anywhere.

## Local development

No AWS access needed:

```bash
cd forms_search/journey_search
uv sync
uv run pytest                     # search, embedding, DynamoDB request, loader and MCP contract
(cd infra && npm ci && npm test)  # checks the CDK stack's security-critical settings
```

Against the deployed table (needs AWS credentials):

```bash
cd forms_search/journey_search
export JOURNEY_SEARCH_TABLE=$(aws ssm get-parameter --name /journey-search/table-name --query Parameter.Value --output text)
uv run journey-search "report a mosquito" --limit 3     # search directly, without MCP
uv run journey-search-server                            # MCP on http://127.0.0.1:8000/mcp, no auth
```

With the server running, in another terminal:

```bash
cd forms_search/journey_search
uv run examples/strands_client.py --url http://127.0.0.1:8000/mcp search "report a mosquito"
```

The local server is unauthenticated and listens on 127.0.0.1 only. Don't
expose it; authentication is AgentCore's job when hosted.

### In a container

```bash
cd forms_search/journey_search
docker build --platform linux/arm64 -t journey-search .
docker run --rm -p 127.0.0.1:8000:8000 -e JOURNEY_SEARCH_TABLE -e AWS_REGION=eu-west-2 \
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN journey-search
curl http://127.0.0.1:8000/ping
```

Credentials are passed at run time for local testing only. The image contains
none; when hosted, the service uses its AgentCore execution role.

## Deploying

Prerequisites: Docker running (CDK builds the image), credentials for the
target account (for example via `gds-cli aws <profile>`), and the account
CDK-bootstrapped in eu-west-2 (it is).

```bash
cd forms_search/journey_search/infra
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
and pushes the image, and AgentCore picks it up. The endpoint, client ID and
secret stay the same unless the runtime or Cognito resources are replaced.

## Loading and updating the catalogue

Embedding the catalogue is a separate step from running the service. After the
first deploy, and whenever `forms_search/data/catalogue.json` changes:

```bash
cd forms_search/journey_search
export JOURNEY_SEARCH_TABLE=$(aws ssm get-parameter --name /journey-search/table-name --query Parameter.Value --output text)
uv run journey-search-load --dry-run                       # what would change
uv run journey-search-load --verify "report a mosquito"    # load, then check search works
```

Only new or changed journeys are re-embedded (each item stores a hash of its
text and the embedding model); journeys removed from the catalogue are deleted
unless you pass `--keep-removed`. New vectors take a short while to become
searchable, which `--verify` waits for. A full load is about 6 Bedrock
embedding requests.

## Giving a team access

1. **Send them [CONNECTING.md](CONNECTING.md).** Its settings table holds the
   current endpoint, token URL and client ID. If the stack is redeployed in a
   way that changes them, update the table from the stack outputs.
2. **Send the client secret separately**, through a secure channel, never in
   the document, chat or email. To read it (needs AWS credentials):

   ```bash
   aws cognito-idp describe-user-pool-client --region eu-west-2 \
     --user-pool-id "$(aws cloudformation describe-stacks --region eu-west-2 --stack-name JourneySearchStack --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" --output text)" \
     --client-id "$(aws cloudformation describe-stacks --region eu-west-2 --stack-name JourneySearchStack --query "Stacks[0].Outputs[?OutputKey=='ClientId'].OutputValue" --output text)" \
     --query UserPoolClient.ClientSecret --output text
   ```

3. **Check the document still works** before sending it, by running every
   command and code block in it against the hosted service. Export the five
   `JOURNEY_SEARCH_*` settings from `CONNECTING.md` (with the secret), keep
   AWS credentials with Bedrock access for the agent examples, then:

   ```bash
   cd forms_search/journey_search
   zsh examples/check_connecting_doc.sh
   ```

   It runs the access check in an empty environment with no AWS credentials,
   the agent example, the Strands integration code on the oldest and newest
   supported Strands versions, the `curl` example, and the documented errors.

To add another consuming team, add a client in `infra/lib/journey-search-stack.ts`
and include it in the runtime's `allowedClients`. To revoke access, remove it
and redeploy.

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
  embed with one model; callers need a token from the one allowed client
  with the `journey-search/search` scope.
- **Latency**: about 300 ms per search inside the service. A new MCP session
  can start a new runtime microVM, which adds a cold start of a few seconds;
  clients that keep their connection open avoid it.

## Known limitations

- Vector search is approximate nearest neighbour, so rankings can differ
  slightly from an exact search.
- About 75 catalogue entries look like test or demo forms. They are loaded
  like any other journey; filtering them is a catalogue decision for later.
- The catalogue comes from `forms_search/data/catalogue.json`, which is built
  by the enrichment step in `forms_search/enrich.py`.

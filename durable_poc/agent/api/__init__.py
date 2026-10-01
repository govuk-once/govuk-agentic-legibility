"""Generalized HTTP+WS+SSE service for the durable_poc Temporal executor.

Sole browser-facing surface for the SvelteKit frontends (`/web`, `/chat`,
`/agentic`, `/voice`). Deterministic routes import only `agent.tools`;
chat/voice routes additionally import `agent.agent.WorkflowAgent`. See
`durable_poc/ARCHITECTURE.md` for the Dual-Path boundary this preserves.
"""

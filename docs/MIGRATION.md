# LangGraph migration notes

## Removed

- fine-grained `StateGraph` nodes and conditional edges;
- LangGraph checkpoint databases and interrupt plumbing;
- the monolithic legacy `AgentState` transport object;
- custom Gemini proxy/client behavior in the production path;
- Critic -> Advicer -> Fixer patch chains;
- model-authored exact-search replacement protocols;
- model-owned browser success claims.

## Replaced with

- five coarse durable stages implemented as ordinary async Python;
- OpenAI Agents SDK for bounded task delegation;
- Codex for all publication workspace execution;
- immutable draft and input layers;
- isolated staging workspaces and atomic artifact promotion;
- deterministic quality gates and hash-bound evidence;
- independent QA roles;
- explicit baseline no-regression comparison.

The old implementation remains available through Git history. Keeping two active
production runtimes would create ambiguous state, test, and support obligations, so
it is intentionally not retained in the migrated branch.

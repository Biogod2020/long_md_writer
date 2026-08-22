# Independent review contract

A qualifying review must be bound to the exact article SHA-256 and publication
revision in the request. It must run with a fresh context, no author transcript,
read-only tools, and an enforced structured-output schema.

The reviewer model supplies findings and a verdict. The execution runtime
supplies provider identity, run ID, isolation mode, tool policy, and timestamps.
A model may not certify its own isolation. Any manuscript or canonical evidence
change invalidates an outstanding request through revision or hash checks.

Reviews submitted through the generic CLI/MCP record command are retained as
unverified evidence and do not satisfy finalization. A trusted runtime adapter
must attest a review only after it actually controlled the isolated execution.

# Runtime Capability Boundary

Technology Intelligence answers what should be chosen and why. A runtime router
answers what can be used here now and how.

The decision graph keeps four entities separate:

- `capability`: the outcome or job that is needed;
- `technology`: a candidate product, framework, protocol, or pattern;
- `interface`: a durable access contract exposed by that technology;
- `runtime`: caller-supplied, short-lived availability and health facts for one
  environment.

Catalog presence links a capability to a candidate and its documented
interfaces. It never proves that one of those interfaces is installed or
usable on the current host.

## Ownership

Technology Intelligence owns:

- contextual comparison of CLI, MCP, API, SDK, and skill-package delivery;
- dated adoption, maturity, security, maintenance, compatibility, and licensing
  evidence;
- a recommendation or bounded trial for the decision profile.

The runtime owner retains:

- installed and enabled state;
- exact executable, server, tool, app, connector, or SDK version;
- authentication, account, tenant, endpoint, and scopes;
- health, latency, permissions, side effects, sandbox, and approval state;
- installation, configuration, invocation, and cleanup.

## Read-only Join

`data/runtime-capability.schema.v1.json` defines an optional caller-supplied
inventory. The query tool validates and attaches matching runtime facts to its
result without persisting them. Never put secrets, tokens, complete environment
variables, private tenant names, or raw credentials in this inventory.

The v1 runtime contract retains `technology_id` for compatibility and accepts
an optional `interface_id` for a more precise join. `provisioning_mode`
distinguishes `preinstalled`, `on-demand`, `bundled`, `remote`, and `unknown`
without pretending that on-demand resolution has already succeeded.

The validator rejects unknown technologies and fields, blank identifiers,
duplicate capability identities, stale or future checks, secret-like keys at
any depth, and impossible enabled or healthy states for an uninstalled or
disabled capability. Runtime facts expire after the schema's short maximum age.

Registry presence is not runtime availability. A CLI on `PATH` is not proof of
working authentication. An MCP `tools/list` response is not approval to call a
tool. An installed SDK is not proof that the configured endpoint, model, or
account can perform the requested operation.

When the user asks to use, install, authenticate, enable, or invoke a selected
surface, hand off to the runtime owner. When the user asks whether CLI, MCP,
API, SDK, or a portable skill is the better durable interface, remain in the
advisor and consume runtime state only as one constraint.

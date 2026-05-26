# AWS DevOps Agent — Claude Plugin using the AWS MCP Server

You are enhanced with the **AWS DevOps Agent**, an AI-powered operational intelligence system for AWS environments. You access it through the **AWS MCP Server** using `aws___call_aws` for standard API operations and `aws___run_script` for streaming APIs (like `SendMessage`).

**Your superpower:** You can combine your local workspace knowledge (files, git, skills, terminal) with the DevOps Agent's cloud knowledge (CloudWatch, X-Ray, IAM, topology) by packing local context into API call parameters. This makes you far more effective than either system alone.


## What you get

The `aws-devops-agent` plugin gives Claude Code:

- **The AWS MCP Server** (`aws___call_aws`, `aws___run_script`, and more) for accessing the AWS DevOps Agent API — investigations, chat, recommendations, AgentSpaces, journal records.
- **Four skills** that auto-route the user's intent:
  - `investigate` — incident root cause (deep, 5–8 min, streamed progress)
  - `chat` — cost / architecture / topology / knowledge (instant)
  - `multi-space` — coordinate across multiple AgentSpaces in one session
  - `setup` — first-time configuration of profiles, spaces, and routing
- **Four slash commands** for explicit control: `/aws-devops-agent:chat`, `/aws-devops-agent:investigate`, `/aws-devops-agent:spaces`, `/aws-devops-agent:cost`.
- **A worked multi-AgentSpace example** at `plugins/aws-devops-agent/examples/multi-space-walkthrough.md`.

## Install

Prerequisite: `uv` must be on `PATH` (the AWS MCP Server is fetched via `uvx`).

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify the MCP proxy works (fetches on first run)
uvx mcp-proxy-for-aws@latest --help
```

Then in Claude Code:

```
/plugin marketplace add aws-samples/sample-aws-devops-agent-claude-plugin
/plugin install aws-devops-agent@aws-devops-tools
/reload-plugins
```

## Try it

```bash
# In your shell, before launching Claude Code:
export AWS_PROFILE=<your-aws-profile>
aws sso login   # or: aws configure
```

Then in Claude Code:

- `aws___call_aws(cli_command="aws devops-agent list-agent-spaces --region us-east-1")` — should return your spaces.
- "Investigate why my ECS service is returning 503s" — auto-invokes the `investigate` skill.
- "What runbooks does the agent have?" — auto-invokes `chat`.
- `/aws-devops-agent:spaces` — list your AgentSpaces explicitly.

## Multiple AgentSpaces

If you have more than one AgentSpace (e.g. prod, staging, knowledge), say "set up the devops agent for multiple accounts" and the `setup` skill walks you through per-space AWS profiles, shell wrappers, and a routing guide. The worked walkthrough at [`plugins/aws-devops-agent/examples/multi-space-walkthrough.md`](plugins/aws-devops-agent/examples/multi-space-walkthrough.md) shows the end-to-end pattern: prod investigation + staging comparison + knowledge-space runbook lookup, all from one Claude Code session.

## Repo layout

```
.
├── .claude-plugin/
│   └── marketplace.json                # this catalog
├── plugins/
│   └── aws-devops-agent/                # the plugin
│       ├── .claude-plugin/plugin.json
│       ├── .mcp.json                    # AWS MCP Server config (uvx mcp-proxy-for-aws)
│       ├── skills/                      # auto-invoked workflows
│       │   ├── investigate/
│       │   ├── chat/
│       │   ├── multi-space/
│       │   └── setup/
│       ├── commands/                    # user-invoked slash commands
│       └── examples/                    # worked walkthroughs
└── README.md                            # this file
```

## Reducing approval fatigue (PreToolUse hooks)

During incident response the plugin can generate 6+ permission prompts per task. To auto-approve **read-only** AWS calls and **chat streaming** while still gating mutations, use the PreToolUse hooks in `examples/hooks/`:

1. Copy the hook scripts from the plugin into your project:
```bash
mkdir -p .claude/hooks
# After marketplace install, hooks are inside the plugin cache:
cp ~/.claude/plugins/cache/aws-devops-tools/aws-devops-agent/*/examples/hooks/aws-allow-reads.sh .claude/hooks/
cp ~/.claude/plugins/cache/aws-devops-tools/aws-devops-agent/*/examples/hooks/aws-allow-chat.sh  .claude/hooks/
```

2. Add to `.claude/settings.json`:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__plugin_aws-devops-agent_aws-mcp__aws___call_aws",
        "hooks": [{"type": "command", "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/aws-allow-reads.sh"}]
      },
      {
        "matcher": "mcp__plugin_aws-devops-agent_aws-mcp__aws___run_script",
        "hooks": [{"type": "command", "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/aws-allow-chat.sh"}]
      }
    ]
  }
}
```

> **Note:** The matcher prefix `mcp__plugin_aws-devops-agent_aws-mcp__` is derived from the plugin name (`aws-devops-agent`) and the MCP server key in `.mcp.json` (`aws-mcp`). If the plugin is renamed, these matchers must be updated.

**What gets auto-approved:** `list-*`, `describe-*`, `get-*` CLI commands, and `send_message` streaming calls.
**What still prompts:** `create-backlog-task`, `create-agent-space`, `update-*`, `delete-*`, and arbitrary `run_script` code.

## Local development

Test the plugin without publishing:

```bash
git clone <this-repo> claude-aws-devops-agent
claude --plugin-dir ./claude-aws-devops-agent/plugins/aws-devops-agent
```

Or load the whole marketplace:

```
/plugin marketplace add ./claude-aws-devops-agent
/plugin install aws-devops-agent@aws-devops-tools
```

After editing skills or commands, run `/reload-plugins` to pick up changes.

Validate before pushing:

```bash
claude plugin validate ./claude-aws-devops-agent
```

## Using with Kiro CLI

This repo can be used directly with Kiro CLI by creating agent spec files in a `.kiro/agents/` directory. The skills in `plugins/aws-devops-agent/skills/` are reused as-is.

### Prerequisites

1. **kiro-cli** installed
2. **uv** installed:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
3. **AWS credentials** configured:
   ```bash
   export AWS_PROFILE=<your-aws-profile>
   aws sso login
   ```

### Step 1 — Clone the repo

```bash
git clone https://github.com/aws-samples/sample-aws-devops-agent-claude-plugin
cd sample-aws-devops-agent-claude-plugin
```

### Step 2 — Create the agent spec directory

```bash
mkdir -p .kiro/agents
```

### Step 3 — Create the agent spec file

Create `.kiro/agents/aws-devops-agent.agent-spec.json`:

```json
{
  "name": "aws-devops-agent",
  "description": "Investigate incidents, optimize costs, review architecture, and map topology with the AWS DevOps Agent.",
  "tools": ["*"],
  "resources": [
    "skill://plugins/aws-devops-agent/skills/investigate/SKILL.md",
    "skill://plugins/aws-devops-agent/skills/chat/SKILL.md",
    "skill://plugins/aws-devops-agent/skills/multi-space/SKILL.md",
    "skill://plugins/aws-devops-agent/skills/setup/SKILL.md"
  ],
  "mcpServers": {
    "aws-mcp": {
      "command": "uvx",
      "timeout": 100000,
      "args": [
        "mcp-proxy-for-aws@latest",
        "https://aws-mcp.us-east-1.api.aws/mcp",
        "--metadata", "AWS_REGION=us-east-1"
      ]
    },
    "devops-agent-chat": {
      "command": "uv",
      "timeout": 200000,
      "args": [
        "run",
        "--with", "mcp[cli]",
        "--with", "boto3",
        "mcp", "run",
        "plugins/aws-devops-agent/tools/chat_server.py"
      ]
    }
  }
}
```

### Step 4 — Start a session

Run `kiro-cli` from the repo root (where the `.kiro` directory is):

```bash
cd sample-aws-devops-agent-claude-plugin
kiro-cli
```

Then load the agent:

```
/agent aws-devops-agent
```

### Verify it works

Check that both MCP servers connected:

```
/mcp
```

You should see `aws-mcp` (with tools like `aws___call_aws`, `aws___run_script`) and `devops-agent-chat` (with `send_message`).

Then try:
- "What runbooks does the agent have?" — uses the `chat` skill
- "Investigate why my ECS service is returning 503s" — uses the `investigate` skill

If you get credential errors, ensure `AWS_PROFILE` is set and `aws sso login` was run before launching `kiro-cli`.

## Contributing

PRs welcome. Skills should keep their `description` frontmatter sharp — that's what the model uses to decide whether to auto-invoke. If you add a skill, also add a one-row entry to `plugins/aws-devops-agent/README.md`.

## License

MIT-0. See [LICENSE](LICENSE).

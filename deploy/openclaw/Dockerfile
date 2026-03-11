FROM node:22-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git python3 build-essential jq \
    && rm -rf /var/lib/apt/lists/*

# Install OpenClaw + mcporter globally
RUN npm install -g pnpm@10 openclaw@2026.3.2 mcporter@0.7.3 \
    && openclaw --version && mcporter --version

# Create non-root user
RUN useradd -m -s /bin/bash openclaw
USER openclaw
WORKDIR /home/openclaw

# Create directory structure
RUN mkdir -p .openclaw/workspace/skills/odoo-crm \
             .openclaw/agents/main/agent \
             .openclaw/agents/main/sessions \
             .mcporter

# Copy config templates (entrypoint will inject env vars at runtime)
COPY --chown=openclaw:openclaw config/openclaw.template.json .openclaw/openclaw.template.json
COPY --chown=openclaw:openclaw config/mcporter.template.json .mcporter/mcporter.template.json
COPY --chown=openclaw:openclaw config/exec-approvals.json .openclaw/exec-approvals.json
COPY --chown=openclaw:openclaw config/workspace/ .openclaw/workspace/

# Copy entrypoint
COPY --chown=openclaw:openclaw entrypoint.sh /home/openclaw/entrypoint.sh
RUN chmod +x /home/openclaw/entrypoint.sh

# Gateway port
EXPOSE 18789

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -sf http://127.0.0.1:18789/health || exit 1

ENTRYPOINT ["/home/openclaw/entrypoint.sh"]

# The subject's machine: Claude Code, uv and the snapshot's Python environment, user anthony, network shut by
# init-firewall.sh at start. Built with the snapshot as the context, so the venv's editable installs point at
# /home/anthony/j-lens-mean, where each run mounts its own copy of the repo:
#
#   docker build -t sb-subject -f container/Dockerfile --build-context ctx=container snapshot/
FROM ubuntu:24.04

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        git curl ca-certificates iptables ipset iproute2 dnsutils jq less ripgrep procps tmux gosu \
    && rm -rf /var/lib/apt/lists/* \
    && userdel -r ubuntu \
    && useradd -m -u 1000 -s /bin/bash anthony

RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python UV_PROJECT_ENVIRONMENT=/opt/jlm-venv UV_LINK_MODE=copy
RUN mkdir -p /opt/uv-python /opt/jlm-venv && chown anthony:anthony /opt/uv-python /opt/jlm-venv

USER anthony
WORKDIR /home/anthony/j-lens-mean
COPY --chown=anthony:anthony . .
RUN uv sync --frozen && uv cache clean
# the mounted repo replaces this copy; its .venv is a symlink to /opt/jlm-venv (launch.sh)
RUN rm -rf /home/anthony/j-lens-mean/* /home/anthony/j-lens-mean/.[!.]*

# the Claude Code version every run so far used (2.1.304, desktop, 2026-10-20); a rebuild would otherwise take the latest
ARG CLAUDE_VERSION=2.1.304
RUN curl -fsSL https://claude.ai/install.sh | bash -s $CLAUDE_VERSION && /home/anthony/.local/bin/claude --version > /home/anthony/.local/claude-version
ENV PATH=/home/anthony/.local/bin:$PATH
RUN git config --global user.name Anthony && git config --global user.email 136634882+Tony-Gon@users.noreply.github.com \
    && git config --global init.defaultBranch main

USER root
# a host whose uid is not 1000 (the Mac: 501) mounts the repo under another owner, which git refuses
RUN git config --system --add safe.directory /home/anthony/j-lens-mean
COPY --from=ctx init-firewall.sh entrypoint.sh /usr/local/sbin/
# sourced before each Bash command (CLAUDE_ENV_FILE, launch.sh): keeps the API proxy wiring out of the subject's shell
COPY --from=ctx --chmod=644 shell-env.sh /etc/claude-shell-env.sh
# root-only: their comments name the metric server, the API proxy and the container marker (pilots/harness-redteam.md)
RUN chmod 700 /usr/local/sbin/init-firewall.sh /usr/local/sbin/entrypoint.sh
ENTRYPOINT ["/usr/local/sbin/entrypoint.sh"]

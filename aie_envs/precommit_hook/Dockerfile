# precommit_hook (the post's Pre-commit Hook) from agent-interp-envs (MIT, 310c03f; see ../LICENSE.agent-interp-envs),
# rebuilt for our Inspect harness: the agent loop runs on the host, so this image holds only the task.
# As upstream's Dockerfile: python:3.11-slim + git/make/gcc/libc6-dev; the same pip set (mypy==1.20.2 and pinned stubs,
# ruff, pytest, pyyaml, python-dotenv, pydantic); apply_patch on PATH; git identity; a non-root `dev` user; /opt
# root-only (chmod 700). Task sources sit under /opt/task as upstream and are copied into /agent at episode start.
# Differences: upstream's harness package isn't installed (it was pip-installed into the system interpreter, so the
# agent's `pip list` showed it and its dependencies); only src_258 is baked (the variant default.yaml uses; upstream
# also bakes src_0 / src_602 and generates intermediates, all root-only).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /agent

# Plain-HTTP apt downloads arrive corrupted on our Colima network (agent 8's fix); the HTTPS mirror is clean.
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update -o Acquire::Retries=5 -o Acquire::http::Pipeline-Depth=0 \
    && apt-get install -y --no-install-recommends -o Acquire::Retries=5 -o Acquire::http::Pipeline-Depth=0 \
        git make gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git config --global user.email "container@modal" && git config --global user.name "Container" \
    && git config --global --add safe.directory '*'

RUN pip install --no-cache-dir "pytest>=7.0" pyyaml python-dotenv ruff "pydantic>=2.0" "mypy==1.20.2" \
    "types-PyYAML==6.0.12.20260518" "types-requests==2.33.0.20260518"

COPY apply_patch.py /opt/apply_patch.py
RUN chmod +x /opt/apply_patch.py && install -m 755 /opt/apply_patch.py /usr/local/bin/apply_patch

COPY pyproject.toml /opt/task/pyproject.toml
COPY src_258 /opt/task/src_258
COPY score.py score_run.py setup_workspace.py /opt/

RUN useradd -m -s /bin/bash dev && chown -R dev:dev /agent && chmod 700 /opt && chmod -R go-rwx /opt

CMD ["tail", "-f", "/dev/null"]

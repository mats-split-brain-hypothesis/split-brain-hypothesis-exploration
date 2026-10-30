#!/bin/bash
# One-time (idempotent) setup on any machine: the venv, then the pinned WorkspaceBench
# checkout installed into it. Run from anywhere:  bash tools/bootstrap.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh

uv sync
WSBENCH_COMMIT=$(.venv/bin/python -c "from umot.provenance import WSBENCH_COMMIT; print(WSBENCH_COMMIT)")
if [ ! -d third_party/workspace-bench ]; then
  git clone -q https://github.com/camilablank/workspace-bench third_party/workspace-bench
fi
git -C third_party/workspace-bench fetch -q origin
git -C third_party/workspace-bench checkout -q "$WSBENCH_COMMIT"
uv pip install --python .venv/bin/python --no-deps -e third_party/workspace-bench
.venv/bin/python -c "import wsbench, umot, jlens; print('bootstrap OK, wsbench @', '$WSBENCH_COMMIT'[:7])"

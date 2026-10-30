"""Share out/ through the project's private Hugging Face dataset repo (src/jlm/hfdata.py).

  python tools/hfdata.py create                       # once: make the repo (private)
  python tools/hfdata.py status [eval ...]            # what differs, per top-level dir
  python tools/hfdata.py push [--dry-run] [eval/typo ...]   # default: captures eval screen concept-labels analysis
  python tools/hfdata.py pull [--dry-run] [captures ...]    # ctx and lens only when named

Repo id: env JLM_HF_DATASET (owner/name), else ``hfdata.REPO``. Log in first: ``hf auth login`` or HF_TOKEN.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # this checkout's jlm, in any worktree

from jlm.hfdata import main

if __name__ == "__main__":
    sys.exit(main())

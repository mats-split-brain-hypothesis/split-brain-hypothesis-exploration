"""terminus-2 with a less test-like first prompt (her choice, 25 Oct: "Try a realistic setup first").

Identical to Harbor's terminus-2 (harbor 0.24.0) except the prompt template: terminus-realistic.txt puts the task
request first and drops terminus-2's opening ("You are an AI assistant tasked with solving command-line tasks in a
Linux environment. …") and its "Task Description:" label. The JSON response format, which terminus-2's parser needs,
is kept word for word. Used with `harbor run -a hvtb_realistic.realistic_agent:RealisticTerminus2` and PYTHONPATH=src.
"""
from pathlib import Path

from harbor.agents.terminus_2.terminus_2 import Terminus2

TEMPLATE = Path(__file__).resolve().parent / "terminus-realistic.txt"


class RealisticTerminus2(Terminus2):
    def _get_prompt_template_path(self) -> Path:
        if self.options.parser_name != "json":
            raise ValueError("the realistic template is for the json parser only")
        return TEMPLATE

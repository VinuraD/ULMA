from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


EVALSET_PATH = Path(__file__).with_name("evalset.json")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_evalset_json_is_valid():
    """Ensure evalset.json exists and is well-formed with required keys."""
    assert EVALSET_PATH.exists(), "evalset.json is missing"
    data = json.loads(EVALSET_PATH.read_text(encoding="utf-8"))
    assert "eval_set_id" in data
    assert "eval_cases" in data
    assert isinstance(data["eval_cases"], list) and data["eval_cases"], "eval_cases must be a non-empty list"


@pytest.mark.asyncio
async def test_agent_evalset_runs_if_adk_available():
    """
    Run a light evaluation using google-adk if available; otherwise skip to keep tests green.
    """
    if importlib.util.find_spec("google.adk") is None:
        pytest.skip("google.adk not available; skipping agent evaluation")

    try:
        from google.adk.evaluation.agent_evaluator import AgentEvaluator
        import ulma_agents.sub_agents.identity_agent  # noqa: F401
    except ModuleNotFoundError:
        pytest.skip("ulma_agents identity_agent not present; skipping agent evaluation")

    await AgentEvaluator.evaluate(
        agent_module="ulma_agents.front",  # contains an `agent` symbol
        eval_dataset_file_path_or_dir=str(EVALSET_PATH),
    )

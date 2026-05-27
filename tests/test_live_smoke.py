import os
import pytest

pytestmark = pytest.mark.live


@pytest.mark.skipif(not os.environ.get("NVIDIA_API_KEY"),
                    reason="NVIDIA_API_KEY not set")
def test_live_run_produces_recommendation():
    from main import run
    verdict = run("2330")
    assert "RECOMMENDATION:" in verdict.upper()

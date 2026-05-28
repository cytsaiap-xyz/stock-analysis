import os
import pytest

pytestmark = pytest.mark.live


@pytest.mark.skipif(not os.environ.get("NVIDIA_API_KEY"),
                    reason="NVIDIA_API_KEY not set")
def test_live_run_produces_recommendation():
    from main import run
    verdict = run("2330")
    # The Chair now answers in Traditional Chinese: "建議: 買進|持有|賣出".
    assert "建議" in verdict
    assert any(word in verdict for word in ("買進", "持有", "賣出"))

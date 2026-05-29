import os
import pytest

from committee.config import API_KEY_ENV

pytestmark = pytest.mark.live


@pytest.mark.skipif(not os.environ.get(API_KEY_ENV),
                    reason="{} not set (active LLM provider's key)".format(API_KEY_ENV))
def test_live_run_produces_recommendation():
    from main import run
    verdict = run("2330")
    # The Chair now answers in Traditional Chinese: "建議: 買進|持有|賣出".
    assert "建議" in verdict
    assert any(word in verdict for word in ("買進", "持有", "賣出"))

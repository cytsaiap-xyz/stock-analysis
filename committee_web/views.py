from django.conf import settings
from django.http import FileResponse, JsonResponse

from committee.config import REFLECTION_PASSES
from committee.markets import get_profile

from committee_web.run import safe_market

_INDEX = settings.BASE_DIR / "web" / "static" / "index.html"


def index(request):
    return FileResponse(open(_INDEX, "rb"), content_type="text/html")


def committee_info(request):
    profile = get_profile(safe_market(request.GET.get("market", "tw")))
    c = profile.committee
    names = profile.labels.agent_names

    def info(a, group):
        return {"name": a.name, "label": names.get(a.name, a.name),
                "model": a.model, "tools": list(a.tool_names), "group": group}

    return JsonResponse({
        "market": profile.market,
        "research": [info(a, "research") for a in c.research],
        "challengers": [info(a, "challengers") for a in c.challengers],
        "chair": info(c.chair, "chair"),
        "verifier": info(c.verifier, "verifier"),
        "phase_names": profile.labels.phase_names,
        "agent_names": names,
        "reflection_passes": REFLECTION_PASSES,
        "ui": profile.ui,
    })

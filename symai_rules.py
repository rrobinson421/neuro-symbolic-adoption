# symai_rules.py
from symai import Symbol
from typing import Any

class MatchEngine(Symbol):
    """
    Symbolic rule engine for calculating match scores.
    Accepts either a Pydantic ParentPreferences instance or a plain dict.
    """

    def _normalize_parent(self, parent: Any) -> dict:
        # If parent is a Pydantic model with model_dump, use it.
        if hasattr(parent, "model_dump"):
            pd = parent.model_dump()
            # normalize text fields
            if pd.get("location_pref"):
                pd["location_pref"] = [str(x).lower() for x in pd["location_pref"]]
            if pd.get("ethnicity_pref"):
                pd["ethnicity_pref"] = [str(x).lower() for x in pd["ethnicity_pref"]]
            if pd.get("health_acceptance") and isinstance(pd["health_acceptance"], str):
                pd["health_acceptance"] = pd["health_acceptance"].lower()
            return pd
        # assume dict-like
        p = dict(parent)
        if p.get("location_pref"):
            p["location_pref"] = [str(x).lower() for x in p["location_pref"]]
        if p.get("ethnicity_pref"):
            p["ethnicity_pref"] = [str(x).lower() for x in p["ethnicity_pref"]]
        if p.get("health_acceptance") and isinstance(p["health_acceptance"], str):
            p["health_acceptance"] = p["health_acceptance"].lower()
        return p

    def score(self, parent: Any, child: dict) -> float:
        """
        Returns a score (float). 0 means hard-filter excluded.
        """
        score = 0.0
        p = self._normalize_parent(parent)

        # Child fields normalization
        child_age = int(child.get("age", 0))
        child_eth = str(child.get("ethnicity", "")).lower()
        child_health = str(child.get("current_health", "")).lower()
        child_siblings = str(child.get("siblings", "")).lower()
        child_location = str(child.get("location", "")).lower()

        # --------------------
        # HARD FILTERS
        # --------------------
        # Age
        if p.get("age_min") is not None:
            try:
                if child_age < int(p["age_min"]):
                    return 0.0
            except Exception:
                pass

        if p.get("age_max") is not None:
            try:
                if child_age > int(p["age_max"]):
                    return 0.0
            except Exception:
                pass

        # Siblings
        if (p.get("accept_siblings") is False) and (child_siblings in ("yes", "true", "1")):
            return 0.0

        # Health policy (HARD for 'healthy', restrictive for 'mild')
        ha = p.get("health_acceptance", "any")
        if ha == "healthy":
            # require 'healthy' in current health text
            if "healthy" not in child_health and "stable" not in child_health and "good" not in child_health:
                return 0.0
        elif ha == "mild":
            # allow mild conditions, exclude 'serious' or 'critical'
            if "serious" in child_health or "critical" in child_health or "requires" in child_health:
                return 0.0
        elif ha == "serious":
            # parent explicitly accepts serious — no exclusion
            pass
        else:
            # 'any' => accept everything
            pass

        # --------------------
        # SOFT SCORING
        # --------------------
        # 1) Age fit (higher is better)
        if p.get("age_min") is not None and p.get("age_max") is not None:
            try:
                target = (int(p["age_min"]) + int(p["age_max"])) / 2.0
                age_score = 1.0 - (abs(child_age - target) / 20.0)
                score += max(age_score, 0.0)
            except Exception:
                pass

        # 2) Ethnicity preference (small boost)
        if p.get("ethnicity_pref"):
            # p["ethnicity_pref"] expected normalized lower-case
            if child_eth in p["ethnicity_pref"]:
                score += 0.35

        # 3) Health acceptance bonuses
        if ha == "any":
            score += 0.15
        elif ha == "serious":
            # parents willing to take serious cases get bonus for matches with serious needs
            if "serious" in child_health or "chronic" in child_health:
                score += 0.35
        elif ha == "healthy":
            # bonus for healthy matches (we already filtered non-healthy)
            score += 0.25
        elif ha == "mild":
            score += 0.1

        # 4) Location preference (small boost)
        if p.get("location_pref"):
            # location_pref is a list of normalized substrings to match
            if any(loc in child_location for loc in p["location_pref"]):
                score += 0.2

        return score



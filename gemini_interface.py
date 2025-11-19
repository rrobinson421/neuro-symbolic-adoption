# gemini_interface.py
from google import genai
from pydantic import BaseModel, Field
from typing import List, Optional
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Gemini client (gemini-2.5-flash used here; change if needed)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

class ParentPreferences(BaseModel):
    age_min: Optional[int] = Field(default=None, description="Minimum acceptable child age.")
    age_max: Optional[int] = Field(default=None, description="Maximum acceptable child age.")
    ethnicity_pref: List[str] = Field(default_factory=list, description="Preferred ethnicities (can be empty).")
    health_acceptance: str = Field(
        default="any",
        description="'any', 'mild', 'healthy', or 'serious' health conditions accepted."
    )
    accept_siblings: bool = Field(default=True, description="Whether the parent accepts sibling groups.")
    location_pref: List[str] = Field(default_factory=list, description="Preferred child locations.")

# default fallback
DEFAULT_PREFERENCES = ParentPreferences()

# synonyms mapping for health_acceptance
_HEALTH_SYNONYMS = {
    "any": {"any", "no preference", "no preference on health", "no health preference", "open", "open to any"},
    "mild": {"mild", "mild conditions", "minor", "minor health issues", "some health issues ok"},
    "healthy": {"healthy", "only healthy", "no health problems", "no issues", "prefer healthy", "must be healthy"},
    "serious": {"serious", "serious conditions", "chronic", "requires care", "special needs", "serious medical"}
}

def _normalize_health_value(v: Optional[str], user_text: str = "") -> str:
    """
    Map free-form health_acceptance (from Gemini) or user's free text into canonical:
    'any' | 'mild' | 'healthy' | 'serious'
    """
    if not v:
        # fallback to probing the user_text for cues
        check = (user_text or "").lower()
    else:
        check = str(v).lower()

    # direct matching
    for canonical, synonyms in _HEALTH_SYNONYMS.items():
        for syn in synonyms:
            if syn in check:
                return canonical

    # some heuristics
    if "healthy" in check or "no siblings" in check and "healthy" in check:
        return "healthy"
    if "mild" in check or "minor" in check:
        return "mild"
    if "serious" in check or "special needs" in check or "chronic" in check:
        return "serious"

    # default
    return "any"

def _normalize_list_of_strings(lst):
    if not lst:
        return []
    return [str(x).lower() for x in lst]

def interpret_preferences(user_text: str) -> ParentPreferences:
    """
    Convert natural language -> ParentPreferences using Gemini structured response.
    Returns a ParentPreferences instance (fallback DEFAULT_PREFERENCES on error).
    """
    prompt = f"""
Convert the following parent description into a structured JSON object matching
the schema provided. Extract meaning even if the parent uses natural language.

Parent description:
{user_text}

Return ONLY valid JSON that matches this schema.
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": ParentPreferences.model_json_schema(),
            },
        )

        # response.text contains the JSON string of the validated output
        prefs = ParentPreferences.model_validate_json(response.text)

        # Normalize location & ethnicity lists
        prefs.location_pref = _normalize_list_of_strings(prefs.location_pref)
        prefs.ethnicity_pref = _normalize_list_of_strings(prefs.ethnicity_pref)

        # Normalize health_acceptance via heuristics + returned value
        prefs.health_acceptance = _normalize_health_value(prefs.health_acceptance, user_text)

        # normalize accept_siblings boolean (ensure not None)
        if prefs.accept_siblings is None:
            prefs.accept_siblings = True

        return prefs

    except Exception as e:
        print(f"Gemini failed to interpret preferences: {e}")
        print("Using default preferences.\n")
        return DEFAULT_PREFERENCES

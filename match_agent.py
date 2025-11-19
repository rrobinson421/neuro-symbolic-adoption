# match_agent.py
import pandas as pd
from gemini_interface import interpret_preferences, ParentPreferences, DEFAULT_PREFERENCES
from symai_rules import MatchEngine
import os

DATA_PATH = os.path.join("data", "children.csv")

def load_children_db(path: str = DATA_PATH) -> pd.DataFrame:
    """Load child data from CSV."""
    return pd.read_csv(path)

def print_children(children: pd.DataFrame):
    print("\n--- Current Children in Database ---\n")
    for _, c in children.iterrows():
        print(
            f"{c['child_id']}: {c['name']}, Age {c['age']}, "
            f"{c['ethnicity']}, Health {c['current_health']}, "
            f"Siblings: {c['siblings']}, Location: {c['location']}"
        )
    print("\n------------------------------------\n")

def prefs_to_dict(prefs: ParentPreferences) -> dict:
    """
    Convert Pydantic model to plain dict, ensuring normalization of keys/values used by MatchEngine.
    """
    d = prefs.model_dump()
    # normalize strings/lists
    d["location_pref"] = [str(x).lower() for x in d.get("location_pref") or []]
    d["ethnicity_pref"] = [str(x).lower() for x in d.get("ethnicity_pref") or []]
    d["health_acceptance"] = (d.get("health_acceptance") or "any").lower()
    return d

def chat_loop():
    children = load_children_db()
    engine = MatchEngine()

    print("\n====================================")
    print(" ADOPTION NEURO-SYMBOLIC MATCHMAKER ")
    print("====================================\n")
    print_children(children)

    while True:
        user_text = input("Enter parent preferences (or 'quit'): ").strip()
        if user_text.lower() in ("quit", "exit"):
            print("\nExiting matchmaker. Goodbye!\n")
            break

        # Use Gemini structured interface (returns ParentPreferences)
        prefs_obj = interpret_preferences(user_text)
        if prefs_obj is None:
            print("Could not interpret preferences; using defaults.\n")
            prefs_obj = DEFAULT_PREFERENCES

        print("\nInterpreted Preferences:")
        print(prefs_obj)
        print()

        # Score children
        matches = []
        for _, child in children.iterrows():
            # pass the Pydantic model directly (MatchEngine handles both)
            s = engine.score(prefs_obj, child)
            if s > 0:
                matches.append((s, child))

        matches.sort(reverse=True, key=lambda x: x[0])

        print("\nTop Matches:\n")
        if not matches:
            print("No suitable matches found.\n")
            continue

        for i, (score, child) in enumerate(matches[:10], start=1):
            print(f"{i}. {child['name']} (score {score:.2f})")
            print(
                f"   Age {child['age']}, Ethnicity {child['ethnicity']}, "
                f"Health: {child['current_health']}, Siblings: {child['siblings']}, "
                f"Location: {child['location']}"
            )
            print()

        print("------------------------------------\n")

if __name__ == "__main__":
    chat_loop()

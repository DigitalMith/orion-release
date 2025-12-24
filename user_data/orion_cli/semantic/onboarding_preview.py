from pathlib import Path
import yaml


def generate_onboarding_inputs(data: dict) -> list[str]:
    root = (data or {}).get("semantic_onboarding") or {}
    q = root.get("questionnaire") or {}

    basics = q.get("basics") or {}
    comm = q.get("communication_style") or {}
    prefs = q.get("personal_preferences") or {}

    out: list[str] = []

    def add(s: str):
        s = (s or "").strip()
        if s:
            out.append(s)

    name = basics.get("name_or_nickname_orion_should_use")
    if name:
        add(f"Orion should address the user as {name}.")

    timezone = basics.get("timezone")
    if timezone:
        tz = str(timezone).strip().replace(" ", "")
        add(f"User's timezone is {tz}.")

    region = basics.get("region_optional")
    if region:
        add(f"User is located in {region}.")

    main_focus = basics.get("main_thing_work_or_focus")
    if main_focus:
        add(f"User's main work or focus is {main_focus}.")

    tone = comm.get("preferred_tone")
    if tone:
        add(f"User prefers a {tone} tone.")

    verbosity = comm.get("verbosity")
    if verbosity:
        add(f"User prefers {verbosity} verbosity by default.")

    step_by_step = comm.get("step_by_step_by_default")
    if isinstance(step_by_step, bool):
        if step_by_step:
            add("User prefers step-by-step instructions by default.")
        else:
            add("User does not prefer step-by-step instructions by default.")

    avoid = comm.get("avoid") or []
    if isinstance(avoid, list):
        for a in avoid:
            if a:
                add(f"User prefers to avoid {a} in responses.")

    loves = comm.get("love_words_or_phrases") or []
    if isinstance(loves, list):
        for w in loves:
            if w:
                add(f"User likes the words or phrases: {w}.")

    hates = comm.get("hate_words_or_phrases") or []
    if isinstance(hates, list):
        for w in hates:
            if w:
                add(f"User dislikes the words or phrases: {w}.")

    foods = prefs.get("favorite_foods") or []
    if isinstance(foods, list):
        for f in foods:
            if f:
                add(f"User likes {f} food.")

    genres = prefs.get("music_favorite_genres") or []
    if isinstance(genres, list):
        for g in genres:
            if g:
                add(f"User enjoys the {g} genre.")

    hobbies = prefs.get("games_hobbies") or []
    if isinstance(hobbies, list):
        for h in hobbies:
            if h:
                add(f"User enjoys {h}.")

    return out


def load_and_generate(path: Path) -> list[str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return generate_onboarding_inputs(data)

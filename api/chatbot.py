import re
import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session, joinedload
from huggingface_hub import InferenceClient

from database.models import Phone

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")
HF_MODEL = os.getenv("HF_MODEL", "openai/gpt-oss-20b:fireworks-ai")

client = InferenceClient(
    provider="auto",
    api_key=HF_TOKEN,
)


PHONE_MODEL_RE = re.compile(
    r'\b(?:galaxy\s+)?(?:s\d+\+?|z\s*fold\s*\d*\+?|z\s*flip\s*\d*\+?|a\s*\d+|note\s*\d+|m\s*\d+|f\s*\d+)\b',
    re.IGNORECASE,
)


def extract_number(text, pattern):
    if not text:
        return 0
    match = re.search(pattern, text)
    return float(match.group(1).replace(",", "")) if match else 0


def extract_display_size(display):
    return extract_number(display, r"([\d\.]+)\s*inches")


def extract_resolution(res):
    match = re.search(r"(\d+)\s*x\s*(\d+)", res or "")
    if match:
        return int(match.group(1)) * int(match.group(2))
    return 0


def extract_android_version(os_str):
    return extract_number(os_str, r"Android\s*(\d+)")


def extract_camera_mp(camera):
    return extract_number(camera, r"(\d+)\s*MP")


def extract_battery_mah(battery):
    return extract_number(battery, r"(\d+)\s*mAh")


def extract_price(price):
    return extract_number(price, r"\$[\s]*([\d,\.]+)")


def extract_release_year(date):
    return extract_number(date, r"(\d{4})")


def rank_phones(phones, field, reverse=True):

    key_map = {
        "display":      lambda p: extract_display_size(p.display or ""),
        "resolution":   lambda p: extract_resolution(p.resolution or ""),
        "os":           lambda p: extract_android_version(p.os or ""),
        "camera":       lambda p: extract_camera_mp(p.rear_camera or ""),
        "camera_count": lambda p: p.rear_camera_count or 0,
        "price":        lambda p: extract_price(p.price or ""),
        "release_date": lambda p: extract_release_year(p.release_date or ""),
        "battery":      lambda p: extract_battery_mah(p.battery or ""),
    }

    extractor = key_map.get(field)
    if not extractor:
        return []

    sorted_phones = sorted(phones, key=extractor, reverse=reverse)
    return sorted_phones[:3]


def detect_ranking_field(question: str):
    q = question.lower()

    if "battery" in q and any(w in q for w in ("best", "most", "which", "longest", "life", "highest")):
        return "battery"
    if "display" in q or "screen size" in q:
        return "display"
    if "resolution" in q:
        return "resolution"
    if "android" in q or " os " in q:
        return "os"
    if "camera count" in q:
        return "camera_count"
    if "camera" in q and any(w in q for w in ("best", "most", "which", "top")):
        return "camera"
    if "price" in q or "cheap" in q or "expensive" in q:
        return "price"
    if "latest" in q or "newest" in q:
        return "release_date"

    return None


def is_reverse(question):
    q = question.lower()
    if "cheap" in q or "lowest" in q:
        return False
    return True


def _name_in_text(name: str, text: str) -> bool:
    escaped = re.escape(name)
    trailing = r'(?![a-z0-9])' if name.endswith('+') else r'(?![a-z0-9+])'
    pattern = r'(?<![a-z0-9])' + escaped + trailing
    return bool(re.search(pattern, text, re.IGNORECASE))


def _candidate_names(phone: Phone) -> list[str]:
    full = phone.name.lower()
    short = full.replace("samsung galaxy ", "")
    seen: set[str] = set()
    result = []
    for n in (full, short):
        if n not in seen:
            seen.add(n)
            result.append(n)
    return result


def find_phone_by_name(question: str, phones: list) -> Phone | None:
    q_lower = question.lower()
    for phone in sorted(phones, key=lambda p: len(p.name), reverse=True):
        for candidate in _candidate_names(phone):
            if _name_in_text(candidate, q_lower):
                return phone
    return None


def find_two_phones(question: str, phones: list) -> tuple[Phone | None, Phone | None]:
    q_lower = question.lower()
    matched = []
    seen: set[int] = set()

    for phone in sorted(phones, key=lambda p: len(p.name), reverse=True):
        if phone.id in seen:
            continue
        for candidate in _candidate_names(phone):
            if _name_in_text(candidate, q_lower):
                matched.append(phone)
                seen.add(phone.id)
                break 

    if len(matched) >= 2:
        return matched[0], matched[1]
    return None, None



SPEC_TOPICS = {
    "camera":      ["camera", "photo", "megapixel", " mp ", "lens", "zoom", "selfie", "aperture", "optical"],
    "battery":     ["battery", "mah", "charging", "battery life", "charge"],
    "display":     ["display", "screen", "amoled", "refresh rate", " hz", "resolution"],
    "performance": ["chipset", "processor", "cpu", "performance", "snapdragon", "exynos", "gpu", "benchmark"],
    "os":          ["android", " os ", "software", "operating system", "update"],
    "build":       ["build", "design", "weight", "material", "color", "glass", "aluminum"],
    "price":       ["price", "cost", "expensive", "cheap", "affordable", "variant", "storage"],
}


def detect_spec_topic(question: str) -> str | None:
    q = question.lower()
    for topic, keywords in SPEC_TOPICS.items():
        for kw in keywords:
            if kw in q:
                return topic
    return None



def format_spec_answer(phone: Phone, topic: str) -> str:
    name = phone.name

    if topic == "camera":
        return (
            f"Camera specs for {name}:\n"
            f"- Rear Camera: {phone.rear_camera or 'N/A'}\n"
            f"- Rear Camera Count: {phone.rear_camera_count or 'N/A'}\n"
            f"- Rear Video: {phone.rear_camera_video or 'N/A'}\n"
            f"- Selfie Camera: {phone.selfie_camera or 'N/A'}\n"
            f"- Selfie Camera Count: {phone.selfie_camera_count or 'N/A'}\n"
            f"- Selfie Video: {phone.selfie_camera_video or 'N/A'}"
        )

    if topic == "battery":
        return f"Battery for {name}: {phone.battery or 'N/A'}"

    if topic == "display":
        return (
            f"Display specs for {name}:\n"
            f"- Display: {phone.display or 'N/A'}\n"
            f"- Resolution: {phone.resolution or 'N/A'}\n"
            f"- Protection: {phone.protection or 'N/A'}"
        )

    if topic == "performance":
        return (
            f"Performance specs for {name}:\n"
            f"- Chipset: {phone.chipset or 'N/A'}\n"
            f"- GPU: {phone.gpu or 'N/A'}\n"
            f"- Battery: {phone.battery or 'N/A'}\n"
            f"- OS: {phone.os or 'N/A'}"
        )

    if topic == "os":
        return f"OS for {name}: {phone.os or 'N/A'}"

    if topic == "build":
        return (
            f"Build specs for {name}:\n"
            f"- Build: {phone.build or 'N/A'}\n"
            f"- Weight: {phone.weight or 'N/A'}\n"
            f"- Colors: {phone.colors or 'N/A'}"
        )

    if topic == "price":
        variants_text = ""
        if phone.variants:
            lines = [f"  - {v.storage}/{v.ram}: {v.price}" for v in phone.variants]
            variants_text = "\nVariants:\n" + "\n".join(lines)
        return f"Price for {name}: {phone.price or 'N/A'}{variants_text}"


    return (
        f"Specs for {name}:\n"
        f"- Chipset: {phone.chipset or 'N/A'}\n"
        f"- Display: {phone.display or 'N/A'}\n"
        f"- Rear Camera: {phone.rear_camera or 'N/A'}\n"
        f"- Battery: {phone.battery or 'N/A'}\n"
        f"- OS: {phone.os or 'N/A'}\n"
        f"- Price: {phone.price or 'N/A'}"
    )


def _section(header: str, rows: list[str]) -> list[str]:
    return [f"\n=== {header} ==="] + rows


def format_comparison(phone1: Phone, phone2: Phone, topic: str | None) -> str:
    n1, n2 = phone1.name, phone2.name
    lines = [f"Comparison: {n1} vs {n2}"]

    if topic == "performance" or topic is None:
        lines += _section("Performance", [
            f"[{n1}]",
            f"  Chipset : {phone1.chipset or 'N/A'}",
            f"  GPU     : {phone1.gpu or 'N/A'}",
            f"  Battery : {phone1.battery or 'N/A'}",
            f"  OS      : {phone1.os or 'N/A'}",
            f"[{n2}]",
            f"  Chipset : {phone2.chipset or 'N/A'}",
            f"  GPU     : {phone2.gpu or 'N/A'}",
            f"  Battery : {phone2.battery or 'N/A'}",
            f"  OS      : {phone2.os or 'N/A'}",
        ])

    if topic == "camera" or topic is None:
        lines += _section("Camera", [
            f"[{n1}]",
            f"  Rear Camera   : {phone1.rear_camera or 'N/A'}",
            f"  Rear Count    : {phone1.rear_camera_count or 'N/A'}",
            f"  Rear Video    : {phone1.rear_camera_video or 'N/A'}",
            f"  Selfie Camera : {phone1.selfie_camera or 'N/A'}",
            f"[{n2}]",
            f"  Rear Camera   : {phone2.rear_camera or 'N/A'}",
            f"  Rear Count    : {phone2.rear_camera_count or 'N/A'}",
            f"  Rear Video    : {phone2.rear_camera_video or 'N/A'}",
            f"  Selfie Camera : {phone2.selfie_camera or 'N/A'}",
        ])

    if topic == "battery" or topic is None:
        lines += _section("Battery", [
            f"  {n1}: {phone1.battery or 'N/A'}",
            f"  {n2}: {phone2.battery or 'N/A'}",
        ])

    if topic == "display" or topic is None:
        lines += _section("Display", [
            f"[{n1}]",
            f"  Size       : {phone1.display or 'N/A'}",
            f"  Resolution : {phone1.resolution or 'N/A'}",
            f"  Protection : {phone1.protection or 'N/A'}",
            f"[{n2}]",
            f"  Size       : {phone2.display or 'N/A'}",
            f"  Resolution : {phone2.resolution or 'N/A'}",
            f"  Protection : {phone2.protection or 'N/A'}",
        ])

    if topic == "price" or topic is None:
        lines += _section("Price", [
            f"  {n1}: {phone1.price or 'N/A'}",
            f"  {n2}: {phone2.price or 'N/A'}",
        ])

    return "\n".join(lines)




def generate_ai_explanation(question: str, ranked_phones: list[Phone], field: str) -> str:
    field_attr_map = {
        "display":      "display",
        "resolution":   "resolution",
        "os":           "os",
        "camera":       "rear_camera",
        "camera_count": "rear_camera_count",
        "price":        "price",
        "release_date": "release_date",
        "battery":      "battery",
    }

    attr = field_attr_map.get(field, field)

    try:
        context_lines = [f"{p.name} - {getattr(p, attr, 'N/A')}" for p in ranked_phones]
        context = "\n".join(context_lines)

        completion = client.chat_completion(
            model=HF_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a smartphone expert. "
                        "Explain rankings clearly and naturally. "
                        "Do NOT change rankings. Only explain why they are ranked this way."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"User question: {question}\n\n"
                        f"Ranking result:\n{context}\n\n"
                        "Explain why these phones are ranked this way in simple terms."
                    ),
                },
            ],
            max_tokens=200,
        )

        content = completion.choices[0].message.content
        return content.strip() if isinstance(content, str) else "Explanation unavailable."

    except Exception:
        return "Explanation unavailable."




def _ranking_answer_line(phone: Phone, field: str, index: int) -> str:
    field_attr_map = {
        "display":      "display",
        "resolution":   "resolution",
        "os":           "os",
        "camera":       "rear_camera",
        "camera_count": "rear_camera_count",
        "price":        "price",
        "release_date": "release_date",
        "battery":      "battery",
    }
    attr = field_attr_map.get(field, field)
    value = getattr(phone, attr, "N/A")
    return f"{index}. {phone.name} — {value}"




def _available_phones_list(phones: list) -> str:
    return "\n".join(f"  - {p.name}" for p in sorted(phones, key=lambda p: p.name))


def handle_chat_question(db: Session, question: str) -> dict:
    phones = db.query(Phone).options(joinedload(Phone.variants)).all()
    q_lower = question.lower()
    is_comparison = (
        "compare" in q_lower
        or " vs " in q_lower
        or "versus" in q_lower
        or "difference between" in q_lower
    )
    if is_comparison:
        phone1, phone2 = find_two_phones(question, phones)

        if phone1 and phone2:
            topic = detect_spec_topic(question)
            return {
                "question": question,
                "intent": "comparison",
                "answer": format_comparison(phone1, phone2, topic),
            }

        single = find_phone_by_name(question, phones)
        if single:
            return {
                "question": question,
                "intent": "self_comparison",
                "answer": (
                    f"There is no point in comparing {single.name} with itself.\n"
                    f"Here are its specs instead:\n\n"
                    + format_spec_answer(single, None)
                ),
            }

        return {
            "question": question,
            "intent": "phone_not_found",
            "answer": (
                "Could not find the phones you mentioned in our database.\n\n"
                "Available phones:\n" + _available_phones_list(phones)
            ),
        }


    phone = find_phone_by_name(question, phones)
    if phone:
        topic = detect_spec_topic(question)
        return {
            "question": question,
            "intent": "phone_spec_lookup",
            "answer": format_spec_answer(phone, topic),
        }

    if PHONE_MODEL_RE.search(question):
        return {
            "question": question,
            "intent": "phone_not_found",
            "answer": (
                "That phone was not found in our database.\n\n"
                "Available phones:\n" + _available_phones_list(phones)
            ),
        }


    field = detect_ranking_field(question)
    if field:
        reverse = is_reverse(question)
        ranked = rank_phones(phones, field, reverse)

        if not ranked:
            return {
                "question": question,
                "intent": "ranking_query",
                "answer": "No data available.",
            }

        answer_lines = [_ranking_answer_line(p, field, i) for i, p in enumerate(ranked, 1)]
        base_answer = "\n".join(answer_lines)
        explanation = generate_ai_explanation(question, ranked, field)

        return {
            "question": question,
            "intent": "ranking_query",
            "answer": f"{base_answer}\n\n💡 Explanation:\n{explanation}",
        }


    return {
        "question": question,
        "intent": "generic",
        "answer": (
            "Ask about specific phone specs (e.g., 'What are the camera specs of the Galaxy S23?'), "
            "battery life rankings (e.g., 'Which phone has the best battery life?'), "
            "or comparisons (e.g., 'How does the Galaxy S23 compare to the S22?')."
        ),
    }

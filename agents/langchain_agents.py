import os
import re
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from sqlalchemy.orm import joinedload

from api.review_generator import generate_phone_review
from database.db import SessionLocal
from database.models import Phone

load_dotenv()

HF_MODEL = os.getenv("HF_MODEL", "openai/gpt-oss-20b")


def as_optional_text(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def build_chat_model() -> ChatHuggingFace:
    llm = HuggingFaceEndpoint(
        model=HF_MODEL,
        task="text-generation",
        provider="auto",
        max_new_tokens=512,
        do_sample=False,
        temperature=0.2,
    )
    return ChatHuggingFace(llm=llm)


def serialize_phone(phone: Phone) -> str:
    variants_text = (
        ", ".join([f"{v.storage} / {v.ram}" for v in phone.variants])
        if phone.variants
        else "No storage/RAM variant information available."
    )

    return f"""
Phone Name: {phone.name}
Brand: {phone.brand}
Display: {phone.display}
Resolution: {phone.resolution}
Protection: {phone.protection}
Chipset: {phone.chipset}
GPU: {phone.gpu}
OS: {phone.os}
Rear Camera Count: {phone.rear_camera_count}
Rear Camera Specs: {phone.rear_camera}
Rear Camera Video: {phone.rear_camera_video}
Selfie Camera Count: {phone.selfie_camera_count}
Selfie Camera Specs: {phone.selfie_camera}
Selfie Camera Video: {phone.selfie_camera_video}
Battery: {phone.battery}
Weight: {phone.weight}
Build: {phone.build}
Colors: {phone.colors}
Price: {phone.price}
Release Date: {phone.release_date}
Variants: {variants_text}
Source URL: {phone.phone_url}
""".strip()


def get_all_phones():
    db = SessionLocal()
    try:
        return (
            db.query(Phone)
            .options(joinedload(Phone.variants))
            .order_by(Phone.name)
            .all()
        )
    finally:
        db.close()


def find_phone_by_name_fragment(text: str) -> Phone | None:
    phones = get_all_phones()
    text_lower = text.lower()

    for phone in phones:
        if phone.name.lower() in text_lower:
            return phone

    for phone in phones:
        short_name = phone.name.lower().replace("samsung galaxy ", "")
        if short_name in text_lower:
            return phone

    return None


def find_two_phones_for_comparison(text: str) -> tuple[Phone | None, Phone | None]:
    phones = get_all_phones()
    text_lower = text.lower()

    matched = []
    seen = set()

    for phone in phones:
        full_name = phone.name.lower()
        short_name = full_name.replace("samsung galaxy ", "")

        if full_name in text_lower or short_name in text_lower:
            if phone.id not in seen:
                matched.append(phone)
                seen.add(phone.id)

    if len(matched) >= 2:
        return matched[0], matched[1]

    return None, None


def requested_count_from_query(query: str, default: int = 3) -> int:
    match = re.search(r"\b(\d+)\b", query)
    if match:
        return max(1, min(int(match.group(1)), 10))
    return default


def parse_release_date_to_datetime(release_date: Any) -> datetime | None:
    release_date_text = as_optional_text(release_date)
    if not release_date_text:
        return None

    text = release_date_text.strip()

    patterns = [
        r"(\d{4}),\s+([A-Za-z]+)\s+(\d{1,2})",
        r"(\d{4}),\s+([A-Za-z]+)",
        r"(\d{4})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue

        try:
            if len(match.groups()) == 3:
                year, month_name, day = match.groups()
                return datetime.strptime(f"{year} {month_name} {day}", "%Y %B %d")

            if len(match.groups()) == 2:
                year, month_name = match.groups()
                return datetime.strptime(f"{year} {month_name} 1", "%Y %B %d")

            if len(match.groups()) == 1:
                year = match.group(1)
                return datetime.strptime(f"{year} January 1", "%Y %B %d")
        except ValueError:
            continue

    return None


def extract_battery_value(battery_text: Any) -> int | None:
    battery_text = as_optional_text(battery_text)
    if not battery_text:
        return None

    match = re.search(r"(\d+)\s*mAh", battery_text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def extract_display_inches(display_text: Any) -> float | None:
    display_text = as_optional_text(display_text)
    if not display_text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*inches", display_text, re.IGNORECASE)
    return float(match.group(1)) if match else None


def extract_resolution_score(resolution_text: Any) -> int | None:
    resolution_text = as_optional_text(resolution_text)
    if not resolution_text:
        return None
    match = re.search(r"(\d+)\s*x\s*(\d+)", resolution_text, re.IGNORECASE)
    if not match:
        return None
    width = int(match.group(1))
    height = int(match.group(2))
    return width * height


def extract_price_value(price_text: Any) -> float | None:
    price_text = as_optional_text(price_text)
    if not price_text:
        return None
    match = re.search(r"[\$€£₹]\s*([\d,]+(?:\.\d+)?)", price_text)
    if not match:
        return None
    return float(match.group(1).replace(",", ""))


def extract_weight_value(weight_text: Any) -> float | None:
    weight_text = as_optional_text(weight_text)
    if not weight_text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*g", weight_text, re.IGNORECASE)
    return float(match.group(1)) if match else None


def extract_main_camera_mp(camera_text: Any) -> int | None:
    camera_text = as_optional_text(camera_text)
    if not camera_text:
        return None
    match = re.search(r"(\d+)\s*MP", camera_text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def extract_video_score(video_text: Any) -> int | None:
    video_text = as_optional_text(video_text)
    if not video_text:
        return None

    text = video_text.lower()
    score = 0

    if "8k" in text:
        score += 10000
    elif "4k" in text:
        score += 5000
    elif "1080p" in text:
        score += 1000

    fps_matches = re.findall(r"@(?:\d+/)*(\d+)fps", text)
    if fps_matches:
        score += max(int(fps) for fps in fps_matches)

    if "hdr10+" in text:
        score += 50
    if "gyro-eis" in text:
        score += 25

    return score if score > 0 else None


def build_ranked_output(
    title: str,
    ranked_items: list[tuple[Phone, float | int]],
    formatter,
) -> str:
    if not ranked_items:
        return "No data found."

    lines = [title]
    for idx, (phone, value) in enumerate(ranked_items, start=1):
        lines.append(f"{idx}. {formatter(phone, value)}")
    return "\n".join(lines)


@tool
def lookup_phone_specs(phone_name: str) -> str:

    phone = find_phone_by_name_fragment(phone_name)
    if not phone:
        return "Phone not found in the database."
    return serialize_phone(phone)


@tool
def generate_phone_review_tool(phone_name: str) -> str:

    phone = find_phone_by_name_fragment(phone_name)
    if not phone:
        return "Phone not found in the database."

    review = generate_phone_review(phone)
    return (
        f"Summary: {review['summary']}\n"
        f"Pros: {', '.join(review['pros'])}\n"
        f"Cons: {', '.join(review['cons'])}\n"
        f"Verdict: {review['verdict']}"
    )


@tool
def compare_phones_tool(query: str) -> str:

    phone1, phone2 = find_two_phones_for_comparison(query)
    if not phone1 or not phone2:
        return "I could not identify two phones to compare from the database."

    return (
        f"Phone 1:\n{serialize_phone(phone1)}\n\n"
        f"Phone 2:\n{serialize_phone(phone2)}"
    )


@tool
def best_battery_phone_tool(_: str = "") -> str:

    phones = get_all_phones()
    ranked = []

    for phone in phones:
        value = extract_battery_value(phone.battery)
        if value is not None:
            ranked.append((phone, value))

    if not ranked:
        return "Could not determine the best battery phone from the database."

    ranked.sort(key=lambda item: item[1], reverse=True)
    best_phone, value = ranked[0]

    return (
        f"The phone with the highest listed battery capacity is {best_phone.name}. "
        f"It has {value} mAh. Release date: {best_phone.release_date}. Price: {best_phone.price}."
    )


@tool
def top_battery_phones_tool(query: str) -> str:

    phones = get_all_phones()
    ranked = []

    for phone in phones:
        value = extract_battery_value(phone.battery)
        if value is not None:
            ranked.append((phone, value))

    if not ranked:
        return "No data found."

    ranked.sort(key=lambda item: item[1], reverse=True)
    count = requested_count_from_query(query, default=3)
    top_items = ranked[:count]

    return build_ranked_output(
        f"Top {len(top_items)} phones with the largest listed battery capacities:",
        top_items,
        lambda phone, value: (
            f"{phone.name} - {int(value)} mAh "
            f"(release: {phone.release_date}, price: {phone.price})"
        ),
    )


@tool
def latest_phone_tool(_: str = "") -> str:

    phones = get_all_phones()
    dated_phones = []

    for phone in phones:
        parsed_date = parse_release_date_to_datetime(phone.release_date)
        if parsed_date:
            dated_phones.append((phone, parsed_date))

    if not dated_phones:
        return "Could not determine the latest phone from the database."

    latest_phone = max(dated_phones, key=lambda item: item[1])[0]

    return (
        f"The latest phone currently available in the database is {latest_phone.name}. "
        f"It was released on {latest_phone.release_date}. "
        f"It has a {latest_phone.display}, uses {latest_phone.chipset}, "
        f"has {latest_phone.battery}, and is priced at {latest_phone.price}. "
        f"Variants: "
        + (
            ", ".join([f"{v.storage} / {v.ram}" for v in latest_phone.variants])
            if latest_phone.variants
            else "No variant information available."
        )
    )


@tool
def top_latest_phones_tool(query: str) -> str:

    phones = get_all_phones()
    dated_phones = []

    for phone in phones:
        parsed_date = parse_release_date_to_datetime(phone.release_date)
        if parsed_date:
            dated_phones.append((phone, parsed_date))

    if not dated_phones:
        return "No data found."

    dated_phones.sort(key=lambda item: item[1], reverse=True)
    count = requested_count_from_query(query, default=3)
    top_items = dated_phones[:count]

    return build_ranked_output(
        f"Top {len(top_items)} latest phones in the database:",
        top_items,
        lambda phone, value: (
            f"{phone.name} - released {phone.release_date} "
            f"(battery: {phone.battery}, price: {phone.price})"
        ),
    )


@tool
def top_display_phones_tool(query: str) -> str:

    phones = get_all_phones()
    ranked = []

    for phone in phones:
        value = extract_display_inches(phone.display)
        if value is not None:
            ranked.append((phone, value))

    if not ranked:
        return "No data found."

    ranked.sort(key=lambda item: item[1], reverse=True)
    count = requested_count_from_query(query, default=3)
    top_items = ranked[:count]

    return build_ranked_output(
        f"Top {len(top_items)} phones with the biggest display sizes:",
        top_items,
        lambda phone, value: (
            f"{phone.name} - {value:.1f} inches "
            f"(resolution: {phone.resolution}, release: {phone.release_date})"
        ),
    )


@tool
def top_resolution_phones_tool(query: str) -> str:

    phones = get_all_phones()
    ranked = []

    for phone in phones:
        value = extract_resolution_score(phone.resolution)
        if value is not None:
            ranked.append((phone, value))

    if not ranked:
        return "No data found."

    ranked.sort(key=lambda item: item[1], reverse=True)
    count = requested_count_from_query(query, default=3)
    top_items = ranked[:count]

    return build_ranked_output(
        f"Top {len(top_items)} phones with the highest display resolutions:",
        top_items,
        lambda phone, value: (
            f"{phone.name} - {phone.resolution} "
            f"(display: {phone.display}, release: {phone.release_date})"
        ),
    )


@tool
def top_price_phones_tool(query: str) -> str:

    phones = get_all_phones()
    ranked = []

    for phone in phones:
        value = extract_price_value(phone.price)
        if value is not None:
            ranked.append((phone, value))

    if not ranked:
        return "No data found."

    ranked.sort(key=lambda item: item[1], reverse=True)
    count = requested_count_from_query(query, default=3)
    top_items = ranked[:count]

    return build_ranked_output(
        f"Top {len(top_items)} most expensive phones in the database:",
        top_items,
        lambda phone, value: (
            f"{phone.name} - {phone.price} "
            f"(release: {phone.release_date}, battery: {phone.battery})"
        ),
    )


@tool
def top_weight_phones_tool(query: str) -> str:

    phones = get_all_phones()
    ranked = []

    for phone in phones:
        value = extract_weight_value(phone.weight)
        if value is not None:
            ranked.append((phone, value))

    if not ranked:
        return "No data found."

    ranked.sort(key=lambda item: item[1], reverse=True)
    count = requested_count_from_query(query, default=3)
    top_items = ranked[:count]

    return build_ranked_output(
        f"Top {len(top_items)} heaviest phones in the database:",
        top_items,
        lambda phone, value: (
            f"{phone.name} - {value:.0f} g "
            f"(display: {phone.display}, battery: {phone.battery})"
        ),
    )


@tool
def top_camera_phones_tool(query: str) -> str:

    phones = get_all_phones()
    ranked = []

    for phone in phones:
        value = extract_main_camera_mp(phone.rear_camera)
        if value is not None:
            ranked.append((phone, value))

    if not ranked:
        return "No data found."

    ranked.sort(key=lambda item: item[1], reverse=True)
    count = requested_count_from_query(query, default=3)
    top_items = ranked[:count]

    return build_ranked_output(
        f"Top {len(top_items)} phones with the strongest rear camera megapixel ranking:",
        top_items,
        lambda phone, value: (
            f"{phone.name} - main rear camera {int(value)} MP "
            f"(rear camera count: {phone.rear_camera_count}, video: {phone.rear_camera_video})"
        ),
    )


@tool
def top_video_phones_tool(query: str) -> str:

    phones = get_all_phones()
    ranked = []

    for phone in phones:
        value = extract_video_score(phone.rear_camera_video)
        if value is not None:
            ranked.append((phone, value))

    if not ranked:
        return "No data found."

    ranked.sort(key=lambda item: item[1], reverse=True)
    count = requested_count_from_query(query, default=3)
    top_items = ranked[:count]

    return build_ranked_output(
        f"Top {len(top_items)} phones with the strongest rear video capability ranking:",
        top_items,
        lambda phone, value: (
            f"{phone.name} - {phone.rear_camera_video} "
            f"(rear camera: {phone.rear_camera})"
        ),
    )


chat_model = build_chat_model()

spec_subagent = create_agent(
    model=chat_model,
    tools=[
        lookup_phone_specs,
        best_battery_phone_tool,
        top_battery_phones_tool,
        latest_phone_tool,
        top_latest_phones_tool,
        top_display_phones_tool,
        top_resolution_phones_tool,
        top_price_phones_tool,
        top_weight_phones_tool,
        top_camera_phones_tool,
        top_video_phones_tool,
    ],
    system_prompt=(
        "You are a specification specialist for Samsung smartphones. "
        "Use the provided tools to answer only from the database data. "
        "If the user asks for the latest or newest phone, use the latest phone tools. "
        "If the user asks for battery rankings, use the battery tools. "
        "If the user asks for biggest display, highest resolution, highest price, heaviest weight, best camera, or best video, use the matching ranking tools. "
        "If the user asks for top N, use the ranking tool with the requested count. "
        "Never use markdown tables. "
        "Never format the answer as a table. "
        "Never return JSON. "
        "Never return code blocks. "
        "Use plain text only. "
        "Use short paragraphs or simple numbered lists when helpful. "
        "Keep responses concise, readable, and suitable for JSON and Postman."
    ),
)

review_subagent = create_agent(
    model=chat_model,
    tools=[generate_phone_review_tool],
    system_prompt=(
        "You are a review specialist for Samsung smartphones. "
        "Use the review tool and answer only from the database data. "
        "Never use markdown tables. "
        "Never format the answer as a table. "
        "Never return JSON. "
        "Never return code blocks. "
        "Write in plain text using short paragraphs or simple bullets only when useful. "
        "Keep the answer readable in JSON and Postman."
    ),
)

comparison_subagent = create_agent(
    model=chat_model,
    tools=[compare_phones_tool],
    system_prompt=(
        "You are a comparison specialist for Samsung smartphones. "
        "Use the comparison tool and answer only from the database data. "
        "Never use markdown tables. "
        "Never format the answer as a table. "
        "Never return JSON. "
        "Never return code blocks. "
        "Present the comparison in plain text with short sections or simple bullets. "
        "Keep it clear and readable in JSON and Postman."
    ),
)


@tool
def call_spec_agent(query: str) -> str:

    result = spec_subagent.invoke({"messages": [{"role": "user", "content": query}]})
    return result["messages"][-1].content


@tool
def call_review_agent(query: str) -> str:

    result = review_subagent.invoke({"messages": [{"role": "user", "content": query}]})
    return result["messages"][-1].content


@tool
def call_comparison_agent(query: str) -> str:

    result = comparison_subagent.invoke({"messages": [{"role": "user", "content": query}]})
    return result["messages"][-1].content


supervisor_agent = create_agent(
    model=chat_model,
    tools=[call_spec_agent, call_review_agent, call_comparison_agent],
    system_prompt=(
        "You are the coordinator for a Samsung smartphone assistant. "
        "Route specification questions, latest-phone questions, and ranking questions to the spec agent. "
        "Route review and buying-opinion questions to the review agent. "
        "Route comparison questions to the comparison agent. "
        "Answer only from database-backed tool results. "
        "Do not invent specifications. "
        "Never use markdown tables. "
        "Never format the answer as a table. "
        "Never return JSON. "
        "Never return code blocks. "
        "Return plain text only. "
        "Keep responses clean, concise, and readable in JSON and Postman."
    ),
)


def run_langchain_chat(question: str) -> str:
    result = supervisor_agent.invoke(
        {"messages": [{"role": "user", "content": question}]}
    )
    return result["messages"][-1].content

from database.models import Phone


def as_optional_text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def as_optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def build_variant_summary(phone: Phone) -> str:
    if not phone.variants:
        return "Storage and RAM variant details are not available."

    variant_parts = [f"{variant.storage} / {variant.ram}" for variant in phone.variants]
    return ", ".join(variant_parts)


def build_pros(phone: Phone) -> list[str]:
    pros = []
    chipset = as_optional_text(phone.chipset)
    display = as_optional_text(phone.display)
    resolution = as_optional_text(phone.resolution)
    rear_camera_count = as_optional_int(phone.rear_camera_count)
    battery = as_optional_text(phone.battery)
    os = as_optional_text(phone.os)
    build = as_optional_text(phone.build)

    if chipset:
        pros.append(f"Strong performance with {chipset}.")

    if display and resolution:
        pros.append(f"Sharp display with {display} and {resolution}.")

    if rear_camera_count is not None and rear_camera_count >= 3:
        pros.append(
            f"Versatile rear camera system with {rear_camera_count} cameras."
        )

    if battery and "5000" in battery:
        pros.append(f"Large battery capacity: {battery}.")

    if os and "7 major Android upgrades" in os:
        pros.append("Long software support with up to 7 major Android upgrades.")

    if build:
        pros.append(f"Premium construction: {build}.")

    return pros[:5]


def build_cons(phone: Phone) -> list[str]:
    cons = []
    price = as_optional_text(phone.price)
    weight = as_optional_text(phone.weight)
    selfie_camera_count = as_optional_int(phone.selfie_camera_count)
    rear_camera_count = as_optional_int(phone.rear_camera_count)
    phone_url = as_optional_text(phone.phone_url)

    if price:
        cons.append(f"Premium pricing may not suit all buyers: {price}.")

    if weight:
        cons.append(f"Some users may find the device heavy at {weight}.")

    if selfie_camera_count == 1:
        cons.append("Front camera setup is straightforward rather than highly specialized.")

    if rear_camera_count is not None and rear_camera_count < 3:
        cons.append("Rear camera setup is less versatile than higher-end multi-camera models.")

    if not phone_url:
        cons.append("Source reference link is unavailable.")

    return cons[:4]


def build_summary(phone: Phone) -> str:
    variants_text = build_variant_summary(phone)
    display = as_optional_text(phone.display)
    chipset = as_optional_text(phone.chipset)
    rear_camera = as_optional_text(phone.rear_camera)
    rear_camera_count = as_optional_int(phone.rear_camera_count)
    selfie_camera = as_optional_text(phone.selfie_camera)
    battery = as_optional_text(phone.battery)

    parts = [
        f"{phone.name} is a Samsung smartphone designed for users who want a balanced mix of performance, display quality, and camera capability.",
    ]

    if display:
        parts.append(f"It features a {display} display.")

    if chipset:
        parts.append(f"It is powered by {chipset}.")

    if rear_camera:
        parts.append(
            f"The rear camera system includes {rear_camera_count or 'multiple'} camera(s), while the selfie camera offers {selfie_camera or 'standard front camera performance'}."
        )

    if battery:
        parts.append(f"It is backed by {battery}.")

    parts.append(f"Available storage/RAM variants include: {variants_text}")

    return " ".join(parts)


def build_verdict(phone: Phone) -> str:
    rear_camera_count = as_optional_int(phone.rear_camera_count)
    battery = as_optional_text(phone.battery)

    if rear_camera_count is not None and rear_camera_count >= 4 and battery and "5000" in battery:
        return (
            f"{phone.name} is a strong flagship choice for users who want premium cameras, high-end performance, and long battery life."
        )

    if rear_camera_count is not None and rear_camera_count >= 3:
        return (
            f"{phone.name} is a well-rounded option for users who want strong everyday performance with capable cameras and a polished display."
        )

    return (
        f"{phone.name} is a practical Samsung phone that offers a solid overall experience for general users."
    )


def generate_phone_review(phone: Phone) -> dict:
    return {
        "phone_id": phone.id,
        "name": phone.name,
        "summary": build_summary(phone),
        "pros": build_pros(phone),
        "cons": build_cons(phone),
        "verdict": build_verdict(phone),
    }

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from api.chatbot import handle_chat_question
from api.review_generator import generate_phone_review
from api.schemas import (
    ChatRequest,
    ChatResponse,
    PhoneResponse,
    PhoneReviewResponse,
    PhoneVariantResponse,
)
from database.db import get_db
from database.models import Phone, PhoneVariant
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI(
    title="Samsung Phone Query and Review API",
    description="API for querying Samsung phone specifications, variants, comparisons, reviews, and chatbot responses.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def serialize_phone(phone: Phone) -> dict:
    return {
        "id": phone.id,
        "name": phone.name,
        "brand": phone.brand,
        "display": phone.display,
        "resolution": phone.resolution,
        "protection": phone.protection,
        "chipset": phone.chipset,
        "gpu": phone.gpu,
        "os": phone.os,
        "rear_camera": phone.rear_camera,
        "rear_camera_count": phone.rear_camera_count,
        "rear_camera_video": phone.rear_camera_video,
        "selfie_camera": phone.selfie_camera,
        "selfie_camera_count": phone.selfie_camera_count,
        "selfie_camera_video": phone.selfie_camera_video,
        "battery": phone.battery,
        "weight": phone.weight,
        "build": phone.build,
        "colors": phone.colors,
        "price": phone.price,
        "release_date": phone.release_date,
        "image_url": phone.image_url,
        "phone_url": phone.phone_url,
        "variants": [
            {
                "storage": variant.storage,
                "ram": variant.ram,
                "price": variant.price,
            }
            for variant in phone.variants
        ],
    }


def get_available_phone_names(db: Session) -> list[str]:
    phones = db.query(Phone).order_by(Phone.name).all()
    return [name for phone in phones if isinstance((name := phone.name), str)]


@app.get("/")
def root():
    return {"message": "Samsung Phone Query and Review API is running."}


@app.get("/phone-names")
def get_phone_names(db: Session = Depends(get_db)):
    return get_available_phone_names(db)


@app.get("/phones", response_model=list[PhoneResponse])
def get_all_phones(db: Session = Depends(get_db)):
    phones = (
        db.query(Phone)
        .options(joinedload(Phone.variants))
        .order_by(Phone.id)
        .all()
    )
    return phones


@app.get("/phones/search", response_model=list[PhoneResponse])
def search_phones(
    name: str = Query(..., min_length=1, description="Partial or full phone name"),
    db: Session = Depends(get_db),
):
    phones = (
        db.query(Phone)
        .options(joinedload(Phone.variants))
        .filter(Phone.name.ilike(f"%{name}%"))
        .order_by(Phone.name)
        .all()
    )

    if not phones:
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"No phones found matching: {name}",
                "available_phones": get_available_phone_names(db),
            },
        )

    return phones


@app.get("/phones/compare")
def compare_phones(
    phone1: str = Query(..., min_length=1, description="First phone name"),
    phone2: str = Query(..., min_length=1, description="Second phone name"),
    db: Session = Depends(get_db),
):
    first_phone = (
        db.query(Phone)
        .options(joinedload(Phone.variants))
        .filter(Phone.name.ilike(f"%{phone1}%"))
        .first()
    )

    second_phone = (
        db.query(Phone)
        .options(joinedload(Phone.variants))
        .filter(Phone.name.ilike(f"%{phone2}%"))
        .first()
    )

    if not first_phone:
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"First phone not found: {phone1}",
                "available_phones": get_available_phone_names(db),
            },
        )

    if not second_phone:
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"Second phone not found: {phone2}",
                "available_phones": get_available_phone_names(db),
            },
        )

    return {
        "phone_1": serialize_phone(first_phone),
        "phone_2": serialize_phone(second_phone),
    }


@app.get("/phones/{phone_id}/review", response_model=PhoneReviewResponse)
def get_phone_review(phone_id: int, db: Session = Depends(get_db)):
    phone = (
        db.query(Phone)
        .options(joinedload(Phone.variants))
        .filter(Phone.id == phone_id)
        .first()
    )

    if not phone:
        raise HTTPException(status_code=404, detail="Phone not found")

    return generate_phone_review(phone)


@app.get("/phones/{phone_id}", response_model=PhoneResponse)
def get_phone_by_id(phone_id: int, db: Session = Depends(get_db)):
    phone = (
        db.query(Phone)
        .options(joinedload(Phone.variants))
        .filter(Phone.id == phone_id)
        .first()
    )

    if not phone:
        raise HTTPException(status_code=404, detail="Phone not found")

    return phone


@app.get("/phones/{phone_id}/variants", response_model=list[PhoneVariantResponse])
def get_phone_variants(phone_id: int, db: Session = Depends(get_db)):
    phone = db.query(Phone).filter(Phone.id == phone_id).first()

    if not phone:
        raise HTTPException(status_code=404, detail="Phone not found")

    variants = (
        db.query(PhoneVariant)
        .filter(PhoneVariant.phone_id == phone_id)
        .order_by(PhoneVariant.id)
        .all()
    )

    return variants


@app.post("/chat", response_model=ChatResponse)
def chat_with_system(payload: ChatRequest, db: Session = Depends(get_db)):
    return handle_chat_question(db, payload.question)

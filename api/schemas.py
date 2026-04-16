from typing import List, Optional

from pydantic import BaseModel


class PhoneVariantResponse(BaseModel):
    id: int
    phone_id: int
    storage: str
    ram: str
    price: Optional[str] = None

    class Config:
        from_attributes = True


class PhoneResponse(BaseModel):
    id: int
    name: str
    brand: str

    display: Optional[str] = None
    resolution: Optional[str] = None
    protection: Optional[str] = None

    chipset: Optional[str] = None
    gpu: Optional[str] = None
    os: Optional[str] = None

    rear_camera: Optional[str] = None
    rear_camera_count: Optional[int] = None
    rear_camera_video: Optional[str] = None

    selfie_camera: Optional[str] = None
    selfie_camera_count: Optional[int] = None
    selfie_camera_video: Optional[str] = None

    battery: Optional[str] = None
    weight: Optional[str] = None
    build: Optional[str] = None
    colors: Optional[str] = None

    price: Optional[str] = None
    release_date: Optional[str] = None
    image_url: Optional[str] = None
    phone_url: Optional[str] = None

    variants: List[PhoneVariantResponse] = []

    class Config:
        from_attributes = True


class PhoneReviewResponse(BaseModel):
    phone_id: int
    name: str
    summary: str
    pros: List[str]
    cons: List[str]
    verdict: str


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    question: str
    intent: str
    answer: str

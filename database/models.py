from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database.db import Base


class Phone(Base):
    __tablename__ = "phones"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    brand = Column(String(100), nullable=False, default="Samsung")

    display = Column(String(255), nullable=True)
    resolution = Column(String(255), nullable=True)
    protection = Column(String(255), nullable=True)

    chipset = Column(String(255), nullable=True)
    gpu = Column(String(255), nullable=True)
    os = Column(String(255), nullable=True)

    rear_camera = Column(Text, nullable=True)
    rear_camera_count = Column(Integer, nullable=True)
    rear_camera_video = Column(Text, nullable=True)

    selfie_camera = Column(Text, nullable=True)
    selfie_camera_count = Column(Integer, nullable=True)
    selfie_camera_video = Column(Text, nullable=True)

    battery = Column(String(255), nullable=True)
    weight = Column(String(255), nullable=True)
    build = Column(Text, nullable=True)
    colors = Column(Text, nullable=True)

    price = Column(String(255), nullable=True)
    release_date = Column(String(255), nullable=True)
    image_url = Column(Text, nullable=True)
    phone_url = Column(Text, nullable=True)

    variants = relationship(
        "PhoneVariant",
        back_populates="phone",
        cascade="all, delete-orphan",
    )


class PhoneVariant(Base):
    __tablename__ = "phone_variants"

    id = Column(Integer, primary_key=True, index=True)
    phone_id = Column(Integer, ForeignKey("phones.id"), nullable=False)
    storage = Column(String(100), nullable=False)
    ram = Column(String(100), nullable=False)
    price = Column(String(255), nullable=True)

    phone = relationship("Phone", back_populates="variants")

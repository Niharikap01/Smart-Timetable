from sqlalchemy import Column, Integer, String, Boolean, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.database.session import Base
from app.models.course import RoomType


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    room_number = Column(String(50), unique=True, nullable=False, index=True)
    room_type = Column(SAEnum(RoomType), nullable=False)
    capacity = Column(Integer, nullable=False)
    building = Column(String(100), nullable=True)
    floor = Column(Integer, nullable=True)
    active = Column(Boolean, nullable=False, default=True)

    timetable_sessions = relationship("TimetableSession", back_populates="room")

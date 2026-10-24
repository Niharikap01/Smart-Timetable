"""In-memory occupancy cache for real-time vacancy tracking."""
from __future__ import annotations
from datetime import datetime, time
from typing import Dict, Optional, Any, List


class RoomStatus:
    def __init__(self, room_id: int, room_number: str, room_type: str, capacity: int):
        self.room_id = room_id
        self.room_number = room_number
        self.room_type = room_type
        self.capacity = capacity
        self.status = "FREE"
        self.course: Optional[str] = None
        self.section: Optional[str] = None
        self.teacher: Optional[str] = None
        self.timeslot: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "room_id": self.room_id,
            "room_number": self.room_number,
            "room_type": self.room_type,
            "capacity": self.capacity,
            "status": self.status,
        }
        if self.status == "OCCUPIED":
            d.update({
                "course": self.course,
                "section": self.section,
                "teacher": self.teacher,
                "timeslot": self.timeslot,
            })
        return d


class OccupancyCache:
    """In-memory cache of room occupancy — rebuilt from timetable, queried by dashboard."""

    def __init__(self):
        self._rooms: Dict[int, RoomStatus] = {}
        self._schedule: List[dict] = []

    def load_rooms(self, rooms: List[dict]):
        self._rooms = {}
        for r in rooms:
            self._rooms[r["room_id"]] = RoomStatus(
                r["room_id"], r["room_number"], r["room_type"], r["capacity"]
            )

    def load_schedule(self, sessions: List[dict]):
        self._schedule = sessions

    def update_current(self, now: Optional[datetime] = None) -> List[dict]:
        """Recompute room status based on current day/time. Returns changed rooms."""
        if now is None:
            now = datetime.now()
        day_name = now.strftime("%A")
        current_time = now.time()

        changed = []
        for room in self._rooms.values():
            old_status = room.status
            room.status = "FREE"
            room.course = None
            room.section = None
            room.teacher = None
            room.timeslot = None

            for s in self._schedule:
                if (s["room_id"] == room.room_id
                        and s["day"] == day_name
                        and s["start_time"] <= current_time < s["end_time"]):
                    room.status = "OCCUPIED"
                    room.course = s.get("course_name", "")
                    room.section = s.get("section_name", "")
                    room.teacher = s.get("teacher_name", "")
                    room.timeslot = f"{s['start_time']}-{s['end_time']}"
                    break

            if room.status != old_status:
                changed.append(room.to_dict())

        return changed

    def get_all(self) -> List[dict]:
        return [r.to_dict() for r in self._rooms.values()]

    def get_room(self, room_id: int) -> Optional[dict]:
        r = self._rooms.get(room_id)
        return r.to_dict() if r else None

    def get_summary(self) -> dict:
        total = len(self._rooms)
        occupied = sum(1 for r in self._rooms.values() if r.status == "OCCUPIED")
        free = total - occupied
        labs_free = sum(1 for r in self._rooms.values() if r.room_type == "lab" and r.status == "FREE")
        classrooms_free = sum(1 for r in self._rooms.values() if r.room_type == "lecture" and r.status == "FREE")
        return {
            "total_rooms": total,
            "occupied": occupied,
            "free": free,
            "labs_free": labs_free,
            "classrooms_free": classrooms_free,
        }


# Global singleton
occupancy_cache = OccupancyCache()

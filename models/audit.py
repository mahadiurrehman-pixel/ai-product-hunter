"""API request audit log model."""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from datetime import datetime
from models.base import Base


class APIRequestLog(Base):
    __tablename__ = "api_request_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service = Column(String(50), nullable=False)
    endpoint = Column(String(500), nullable=False)
    method = Column(String(10), nullable=False, default="GET")
    status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Float, nullable=True)
    was_cached = Column(Boolean, default=False)
    cache_key = Column(String(255), nullable=True)
    error_occurred = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    error_type = Column(String(100), nullable=True)
    request_params = Column(Text, nullable=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<APIRequestLog {self.method} {self.endpoint} [{self.status_code}]>"
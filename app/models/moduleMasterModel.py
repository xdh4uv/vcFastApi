
import uuid

from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import DateTime  # for the column type definition
from datetime import datetime, timezone  

from ..core.database import Base

class ModuleMaster(Base):
    __tablename__ = "modules_master"
    __table_args__ = {"schema": "modules"}


    module_id= Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module_name = Column(String(255), nullable=False)
    module_description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))



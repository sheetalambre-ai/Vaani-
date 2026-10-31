from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Meeting(Base):
    __tablename__ = "meetings"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    held_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    raw_input = Column(Text)
    cleaned_transcript = Column(Text)
    utterances = relationship("Utterance", back_populates="meeting", cascade="all, delete-orphan")
    decisions = relationship("Decision", back_populates="meeting", cascade="all, delete-orphan")
    action_items = relationship("ActionItem", back_populates="meeting", cascade="all, delete-orphan")
    corrections = relationship("Correction", back_populates="meeting", cascade="all, delete-orphan")


class Utterance(Base):
    __tablename__ = "utterances"
    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    speaker = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    meeting = relationship("Meeting", back_populates="utterances")


class Decision(Base):
    __tablename__ = "decisions"
    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    statement = Column(Text, nullable=False)
    rationale = Column(Text)
    alternatives_rejected = Column(JSON)
    decided_by = Column(String)
    evidence_quote = Column(Text)
    status = Column(String, default="active")  # active|superseded|conflicted
    embedding = Column(JSON)
    meeting = relationship("Meeting", back_populates="decisions")
    conflicts_as_new = relationship("Conflict", foreign_keys="Conflict.new_decision_id", back_populates="new_decision")
    conflicts_as_old = relationship("Conflict", foreign_keys="Conflict.old_decision_id", back_populates="old_decision")


class ActionItem(Base):
    __tablename__ = "action_items"
    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    task = Column(Text, nullable=False)
    owner = Column(String)
    due_date = Column(String)
    done_definition = Column(Text)
    evidence_quote = Column(Text)
    missing_fields = Column(JSON)
    status = Column(String, default="pending_review")  # pending_review|approved|rejected|created|done
    external_ref = Column(String)
    meeting = relationship("Meeting", back_populates="action_items")
    reminders = relationship("Reminder", back_populates="action_item", cascade="all, delete-orphan")


class Conflict(Base):
    __tablename__ = "conflicts"
    id = Column(Integer, primary_key=True)
    new_decision_id = Column(Integer, ForeignKey("decisions.id"), nullable=False)
    old_decision_id = Column(Integer, ForeignKey("decisions.id"), nullable=False)
    type = Column(String)  # reversal|deadline|scope|resource
    severity = Column(String)  # low|medium|high
    explanation = Column(Text)
    resolution = Column(String, default="open")  # open|accepted_new|kept_old
    new_decision = relationship("Decision", foreign_keys=[new_decision_id], back_populates="conflicts_as_new")
    old_decision = relationship("Decision", foreign_keys=[old_decision_id], back_populates="conflicts_as_old")


class Correction(Base):
    __tablename__ = "corrections"
    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    target_type = Column(String)  # decision|action_item
    target_id = Column(Integer)
    field = Column(String)
    old_value = Column(Text)
    new_value = Column(Text)
    spoken_text = Column(Text)
    meeting = relationship("Meeting", back_populates="corrections")


class Reminder(Base):
    __tablename__ = "reminders"
    id = Column(Integer, primary_key=True)
    action_item_id = Column(Integer, ForeignKey("action_items.id"), nullable=False)
    send_at = Column(DateTime, nullable=False)
    channel = Column(String, default="in_app")
    sent_at = Column(DateTime)
    action_item = relationship("ActionItem", back_populates="reminders")


class Person(Base):
    __tablename__ = "people"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    telegram_chat_id = Column(String)
    email = Column(String)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    read = Column(Boolean, default=False)

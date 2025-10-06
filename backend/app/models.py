import uuid
from datetime import datetime
from typing import Any

from pydantic import EmailStr
from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=40)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=40)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)


# Agent Run and Evaluation Models
class AgentRun(SQLModel, table=True):
    """Stores execution metadata for agent runs.

    Attributes:
        id: Unique identifier for the run
        user_id: Foreign key to the user who initiated the run
        input: The input/prompt provided to the agent
        output: The generated output from the agent
        status: Execution status (pending, running, completed, failed)
        latency_ms: Total execution time in milliseconds
        prompt_tokens: Number of tokens in the input prompt
        completion_tokens: Number of tokens in the completion
        trace_id: Langfuse trace ID for observability correlation
        thread_id: LangGraph thread ID for conversation tracking
        created_at: Timestamp when the run was created
    """

    __tablename__ = "agentrun"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
    )
    input: str = Field(nullable=False)
    output: str | None = Field(default=None)
    status: str = Field(default="pending", max_length=50, index=True)
    latency_ms: int | None = Field(default=None)
    prompt_tokens: int | None = Field(default=None)
    completion_tokens: int | None = Field(default=None)
    trace_id: str | None = Field(default=None, max_length=255, index=True)
    thread_id: str | None = Field(default=None, max_length=255, index=True)
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        index=True,
    )

    # Relationships
    evaluations: list["AgentEvaluation"] = Relationship(
        back_populates="run",
        cascade_delete=True,
    )


class AgentEvaluation(SQLModel, table=True):
    """Stores evaluation metrics for agent runs.

    Attributes:
        id: Unique identifier for the evaluation
        run_id: Foreign key to the associated agent run
        metric_name: Name of the evaluation metric
        score: Numerical score for the metric
        eval_metadata: Additional evaluation data stored as JSON
        created_at: Timestamp when the evaluation was created
    """

    __tablename__ = "agentevaluation"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    run_id: uuid.UUID = Field(
        foreign_key="agentrun.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
    )
    metric_name: str = Field(nullable=False, max_length=255, index=True)
    score: float = Field(nullable=False)
    eval_metadata: Any = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        index=True,
    )

    # Relationships
    run: AgentRun | None = Relationship(back_populates="evaluations")

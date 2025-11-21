"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Literal

class AppUser(BaseModel):
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Unique email address")
    password_hash: str = Field(..., description="BCrypt password hash")
    avatar: Optional[str] = Field(None, description="Avatar URL")
    is_active: bool = Field(True, description="Whether user is active")

class QuizQuestion(BaseModel):
    question: str = Field(..., description="The quiz question text")
    options: List[str] = Field(..., min_items=2, max_items=6, description="Multiple choice options")
    answer_index: int = Field(..., ge=0, le=5, description="Index of the correct option")
    difficulty: Literal['easy','medium','hard'] = Field(..., description="Difficulty level")
    theme: str = Field("jurassic", description="Theme or category")

class QuizResult(BaseModel):
    user_email: EmailStr = Field(..., description="Email of the user who played")
    score: int = Field(..., ge=0, description="Total score achieved")
    total: int = Field(..., ge=1, description="Total number of questions")
    difficulty: Literal['easy','medium','hard'] = Field(..., description="Difficulty played")
    theme: str = Field("jurassic", description="Theme or category")

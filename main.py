import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets

from database import db, create_document, get_documents
from schemas import AppUser, QuizQuestion, QuizResult

app = FastAPI(title="Jurassic Quiz API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple token store in DB (collection: session)
# Token payload: { token, email, expires_at }

class RegisterPayload(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginPayload(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    token: str
    name: str
    email: EmailStr

# Password hashing (sha256 + salt). In production, use bcrypt. Here we keep it dependency-free.
SECRET_SALT = os.getenv("APP_SECRET", "jurassic-salt")

def hash_password(password: str) -> str:
    return hashlib.sha256((SECRET_SALT + password).encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), password_hash)


async def get_current_user(token: Optional[str]) -> Optional[dict]:
    if not token:
        return None
    try:
        sessions = db["session"].find_one({"token": token})
        if not sessions:
            return None
        if sessions.get("expires_at") and sessions["expires_at"] < datetime.now(timezone.utc):
            db["session"].delete_one({"token": token})
            return None
        user = db["appuser"].find_one({"email": sessions["email"]})
        return user
    except Exception:
        return None


@app.get("/")
def root():
    return {"message": "Jurassic Quiz API running"}


@app.post("/auth/register", response_model=TokenResponse)
def register(payload: RegisterPayload):
    existing = db["appuser"].find_one({"email": payload.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = AppUser(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    user_id = create_document("appuser", user)

    token = secrets.token_urlsafe(32)
    db["session"].insert_one({
        "token": token,
        "email": payload.email,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
    })

    return TokenResponse(token=token, name=user.name, email=user.email)


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginPayload):
    user = db["appuser"].find_one({"email": payload.email})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = secrets.token_urlsafe(32)
    db["session"].insert_one({
        "token": token,
        "email": payload.email,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
    })
    return TokenResponse(token=token, name=user.get("name", ""), email=user.get("email"))


@app.post("/auth/logout")
def logout(token: Optional[str] = None):
    if token:
        db["session"].delete_one({"token": token})
    return {"success": True}


# Seed Jurassic quiz questions if empty
JURASSIC_QUESTIONS: List[QuizQuestion] = [
    QuizQuestion(
        question="Ano ang panahon kung kailan namuhay ang mga dinosaur?",
        options=["Jurassic", "Cenozoic", "Precambrian", "Holocene"],
        answer_index=0,
        difficulty="easy",
    ),
    QuizQuestion(
        question="Alin sa mga ito ang isang carnivorous dinosaur?",
        options=["Triceratops", "Brachiosaurus", "Stegosaurus", "Tyrannosaurus Rex"],
        answer_index=3,
        difficulty="easy",
    ),
    QuizQuestion(
        question="Ano ang tawag sa taong nag-aaral ng fossils?",
        options=["Archaeologist", "Paleontologist", "Geologist", "Biologist"],
        answer_index=1,
        difficulty="easy",
    ),
    QuizQuestion(
        question="Anong uri ng dinosaur si Velociraptor?",
        options=["Herbivore", "Carnivore", "Omnivore", "Insectivore"],
        answer_index=1,
        difficulty="medium",
    ),
    QuizQuestion(
        question="Saan natagpuan ang unang fossil ng Archaeopteryx?",
        options=["China", "Germany", "USA", "Argentina"],
        answer_index=1,
        difficulty="medium",
    ),
    QuizQuestion(
        question="Anong katangian ang tumutulong sa mga sauropods na kumain ng matataas na halaman?",
        options=["Mahahabang leeg", "Matutulis na ngipin", "Malalaking pakpak", "Matitibay na sungay"],
        answer_index=0,
        difficulty="medium",
    ),
    QuizQuestion(
        question="Alin ang mas nauna: Triassic, Jurassic, o Cretaceous?",
        options=["Jurassic", "Cretaceous", "Triassic", "Pare-pareho"],
        answer_index=2,
        difficulty="hard",
    ),
    QuizQuestion(
        question="Ano ang pangunahing teorya sa pagkalipol ng mga dinosaur?",
        options=["Pagbaha", "Pagputok ng bulkan", "Pagbangga ng asteroid", "Matinding lamig"],
        answer_index=2,
        difficulty="hard",
    ),
    QuizQuestion(
        question="Anong fossil resin ang madalas nakabihag ng mga insekto mula pa noong sinaunang panahon?",
        options=["Tar", "Amber", "Coal", "Quartz"],
        answer_index=1,
        difficulty="hard",
    ),
]


def seed_questions_if_needed():
    count = db["quizquestion"].count_documents({"theme": "jurassic"})
    if count == 0:
        for q in JURASSIC_QUESTIONS:
            create_document("quizquestion", q)


@app.get("/quiz/questions", response_model=List[QuizQuestion])
def get_questions(difficulty: Optional[str] = None, limit: int = 10):
    seed_questions_if_needed()
    filter_dict = {"theme": "jurassic"}
    if difficulty in ("easy", "medium", "hard"):
        filter_dict["difficulty"] = difficulty
    docs = get_documents("quizquestion", filter_dict, limit)
    # Sanitize for response
    out: List[QuizQuestion] = []
    for d in docs:
        out.append(QuizQuestion(
            question=d.get("question", ""),
            options=d.get("options", []),
            answer_index=d.get("answer_index", 0),
            difficulty=d.get("difficulty", "easy"),
            theme=d.get("theme", "jurassic"),
        ))
    return out


class SubmitPayload(BaseModel):
    user_email: EmailStr
    answers: List[int]
    difficulty: Optional[str] = None


@app.post("/quiz/submit")
def submit_quiz(payload: SubmitPayload):
    seed_questions_if_needed()
    filter_dict = {"theme": "jurassic"}
    if payload.difficulty in ("easy", "medium", "hard"):
        filter_dict["difficulty"] = payload.difficulty

    questions = get_documents("quizquestion", filter_dict, None)
    if not questions:
        raise HTTPException(status_code=400, detail="No questions available")

    total = min(len(questions), len(payload.answers))
    score = 0
    for i in range(total):
        if payload.answers[i] == questions[i].get("answer_index"):
            score += 1

    result = QuizResult(
        user_email=payload.user_email,
        score=score,
        total=total,
        difficulty=(payload.difficulty if payload.difficulty else questions[0].get("difficulty", "easy")),
        theme="jurassic",
    )
    create_document("quizresult", result)

    return {"score": score, "total": total}


@app.get("/quiz/leaderboard")
def leaderboard(limit: int = 10):
    seed_questions_if_needed()
    results = db["quizresult"].find({"theme": "jurassic"}).sort("score", -1).limit(limit)
    data = []
    for r in results:
        data.append({
            "user_email": r.get("user_email"),
            "score": r.get("score"),
            "total": r.get("total"),
            "difficulty": r.get("difficulty"),
            "created_at": r.get("created_at"),
        })
    return data


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

from datetime import datetime, timedelta
from sqlmodel import Session, create_engine, select

from app import crud
from app.core.config import AppEnv, settings
from app.models import AgentEvaluation, AgentRun, User, UserCreate

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = crud.create_user(session=session, user_create=user_in)

    # Create sample agent runs for testing environments (local and staging)
    if settings.APP_ENV in [AppEnv.LOCAL, AppEnv.STAGING]:
        # Check if sample data already exists
        existing_runs = session.exec(select(AgentRun)).first()
        if not existing_runs and user:
            # Create sample agent runs with various statuses
            sample_runs = [
                AgentRun(
                    user_id=user.id,
                    input="What is the weather like today?",
                    output="I don't have access to real-time weather data. Please check a weather service for current conditions.",
                    status="completed",
                    latency_ms=1250,
                    prompt_tokens=45,
                    completion_tokens=89,
                    trace_id="trace_sample_001",
                    created_at=datetime.utcnow() - timedelta(days=2),
                ),
                AgentRun(
                    user_id=user.id,
                    input="Help me write a Python function to calculate fibonacci numbers",
                    output="Here's a Python function using dynamic programming:\n\ndef fibonacci(n):\n    if n <= 1:\n        return n\n    fib = [0, 1]\n    for i in range(2, n + 1):\n        fib.append(fib[i-1] + fib[i-2])\n    return fib[n]",
                    status="completed",
                    latency_ms=2340,
                    prompt_tokens=78,
                    completion_tokens=156,
                    trace_id="trace_sample_002",
                    created_at=datetime.utcnow() - timedelta(days=1),
                ),
                AgentRun(
                    user_id=user.id,
                    input="Analyze this error message: TypeError: 'NoneType' object is not subscriptable",
                    output="This error occurs when you try to access an index or key on a None value. Common causes:\n1. Function returns None instead of expected value\n2. Variable not initialized properly\n3. Failed API call or database query\n\nCheck the stack trace to identify where the None value originates.",
                    status="completed",
                    latency_ms=1890,
                    prompt_tokens=62,
                    completion_tokens=134,
                    trace_id="trace_sample_003",
                    created_at=datetime.utcnow() - timedelta(hours=12),
                ),
                AgentRun(
                    user_id=user.id,
                    input="Generate a complex SQL query with multiple joins",
                    output=None,
                    status="failed",
                    latency_ms=450,
                    prompt_tokens=34,
                    completion_tokens=0,
                    trace_id="trace_sample_004",
                    created_at=datetime.utcnow() - timedelta(hours=6),
                ),
                AgentRun(
                    user_id=user.id,
                    input="Explain the concept of vector databases",
                    output=None,
                    status="running",
                    latency_ms=None,
                    prompt_tokens=28,
                    completion_tokens=None,
                    trace_id="trace_sample_005",
                    created_at=datetime.utcnow() - timedelta(minutes=5),
                ),
            ]

            for run in sample_runs:
                session.add(run)
            session.commit()

            # Create sample evaluations for completed runs
            completed_runs = [r for r in sample_runs if r.status == "completed"]
            sample_evaluations = [
                AgentEvaluation(
                    run_id=completed_runs[0].id,
                    metric_name="relevance",
                    score=0.92,
                    eval_metadata={
                        "evaluator": "llm-as-judge",
                        "model": "gpt-4",
                        "criteria": "Response addresses the user's question",
                    },
                    created_at=datetime.utcnow() - timedelta(days=1, hours=23),
                ),
                AgentEvaluation(
                    run_id=completed_runs[0].id,
                    metric_name="helpfulness",
                    score=0.75,
                    eval_metadata={
                        "evaluator": "llm-as-judge",
                        "model": "gpt-4",
                        "criteria": "Response provides actionable information",
                    },
                    created_at=datetime.utcnow() - timedelta(days=1, hours=23),
                ),
                AgentEvaluation(
                    run_id=completed_runs[1].id,
                    metric_name="code_quality",
                    score=0.88,
                    eval_metadata={
                        "evaluator": "static-analysis",
                        "checks": ["syntax", "performance", "best_practices"],
                        "passed": 8,
                        "total": 9,
                    },
                    created_at=datetime.utcnow() - timedelta(hours=23),
                ),
                AgentEvaluation(
                    run_id=completed_runs[1].id,
                    metric_name="correctness",
                    score=0.95,
                    eval_metadata={
                        "evaluator": "test-execution",
                        "tests_passed": 19,
                        "tests_total": 20,
                    },
                    created_at=datetime.utcnow() - timedelta(hours=23),
                ),
                AgentEvaluation(
                    run_id=completed_runs[2].id,
                    metric_name="accuracy",
                    score=0.90,
                    eval_metadata={
                        "evaluator": "llm-as-judge",
                        "model": "gpt-4",
                        "criteria": "Correctly identifies error cause and solutions",
                    },
                    created_at=datetime.utcnow() - timedelta(hours=11),
                ),
            ]

            for evaluation in sample_evaluations:
                session.add(evaluation)
            session.commit()

"""Database seed script for demo accounts and initial subject."""

import asyncio

from app.core.database import async_session_factory, init_db
from app.core.security import get_password_hash
from app.models.subject import Subject
from app.models.user import User, UserRole


async def seed() -> None:
    print("Initializing database...")
    await init_db()

    async with async_session_factory() as session:
        # 1. Admin
        admin = User(
            email="admin@vivaiq.edu",
            hashed_password=get_password_hash("admin123"),
            full_name="VivaIQ Administrator",
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(admin)

        # 2. Teacher
        teacher = User(
            email="teacher@vivaiq.edu",
            hashed_password=get_password_hash("teacher123"),
            full_name="Prof. Alan Turing",
            role=UserRole.TEACHER,
            is_active=True,
        )
        session.add(teacher)
        await session.flush()

        # 3. Student
        student = User(
            email="student@vivaiq.edu",
            hashed_password=get_password_hash("student123"),
            full_name="Ada Lovelace",
            role=UserRole.STUDENT,
            is_active=True,
        )
        session.add(student)

        # 4. Sample Subject: Computer Systems & Networks
        subject = Subject(
            name="Operating Systems & Concurrency",
            code="CS301",
            description="Process synchronization, deadlock conditions (mutual exclusion, hold and wait, no preemption, circular wait), banker's algorithm, and virtual memory paging.",
            teacher_id=teacher.id,
        )
        session.add(subject)

        await session.commit()
        print("Demo seed data created successfully:")
        print("  - Admin:   admin@vivaiq.edu / admin123")
        print("  - Teacher: teacher@vivaiq.edu / teacher123")
        print("  - Student: student@vivaiq.edu / student123")
        print(f"  - Subject: {subject.name} ({subject.code})")


if __name__ == "__main__":
    asyncio.run(seed())

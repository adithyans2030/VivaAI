"""Comprehensive Demo Seeder for VivaIQ.

Seeds teacher & student accounts, course subject, syllabus materials in ChromaDB,
and realistic completed viva voce sessions (authentic vs. note-reading) with audio.
"""

import asyncio
from datetime import datetime, timezone
import io
from pathlib import Path
import struct
import uuid
import wave

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory, init_db
from app.core.security import get_password_hash
from app.models.audit import AuditLog, ScoreOverride
from app.models.document import Document, IngestionStatus
from app.models.session import AuthenticityLikelihood, SessionStatus, VivaSession
from app.models.subject import Subject
from app.models.turn import Turn
from app.models.user import User, UserRole
from app.services.rag import get_rag_store


def generate_dummy_wav(duration_seconds: float = 2.0) -> bytes:
    """Generate a valid PCM 16-bit 16kHz mono WAV byte string."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        # Generate silence / subtle hum
        num_frames = int(16000 * duration_seconds)
        data = bytearray(num_frames * 2)
        wf.writeframes(bytes(data))
    return buf.getvalue()


async def seed_demo():
    print("\n" + "=" * 60)
    print("[*] VivaIQ Comprehensive Demo Seeder")
    print("=" * 60)

    await init_db()

    async with async_session_factory() as db:
        # 1. Seed Users
        print("\n[1/5] Seeding Users...")
        users_data = [
            ("teacher@vivaiq.edu", "Dr. Alan Turing", "TeacherPass123!", UserRole.TEACHER),
            ("alex@student.edu", "Alex Lovelace", "StudentPass123!", UserRole.STUDENT),
            ("robert@student.edu", "Robert Smith", "StudentPass123!", UserRole.STUDENT),
        ]

        user_map = {}
        for email, full_name, password, role in users_data:
            stmt = select(User).where(User.email == email)
            existing = (await db.execute(stmt)).scalar_one_or_none()
            if not existing:
                u = User(
                    email=email,
                    hashed_password=get_password_hash(password),
                    full_name=full_name,
                    role=role,
                    is_active=True,
                )
                db.add(u)
                await db.flush()
                await db.refresh(u)
                user_map[email] = u
                print(f"  [+] Created {role.value.upper()}: {email} (Password: {password})")
            else:
                user_map[email] = existing
                print(f"  [*] Existing {role.value.upper()}: {email}")

        teacher = user_map["teacher@vivaiq.edu"]
        student_alex = user_map["alex@student.edu"]
        student_robert = user_map["robert@student.edu"]

        # 2. Seed Subject
        print("\n[2/5] Seeding Course Subject...")
        subj_stmt = select(Subject).where(Subject.code == "CS301")
        subject = (await db.execute(subj_stmt)).scalar_one_or_none()
        if not subject:
            subject = Subject(
                name="Operating Systems & Concurrency",
                code="CS301",
                description="Process synchronization, deadlock Coffman conditions, memory paging, and resource allocation.",
                teacher_id=teacher.id,
            )
            db.add(subject)
            await db.flush()
            await db.refresh(subject)
            print(f"  [+] Created Subject: CS301 - {subject.name}")
        else:
            print(f"  [*] Existing Subject: CS301 - {subject.name}")

        # 3. Ingest Course Document into Vector Store
        print("\n[3/5] Ingesting Course Syllabus into RAG Vector Store...")
        doc_stmt = select(Document).where(Document.subject_id == subject.id)
        existing_doc = (await db.execute(doc_stmt)).scalar_one_or_none()

        syllabus_text = """
Course: CS301 Operating Systems
Module 4: Concurrency and Deadlocks

1. Coffman Conditions:
A deadlock state occurs if and only if four necessary conditions hold simultaneously:
- Mutual Exclusion: At least one resource must be held in a non-shareable mode.
- Hold and Wait: A process must be currently holding at least one resource and requesting additional resources that are held by others.
- No Preemption: Resources cannot be forcibly preempted from a process; they can only be released voluntarily after task completion.
- Circular Wait: A closed chain of processes exists such that each process holds at least one resource needed by the next.

2. Banker's Algorithm:
Developed by Edsger Dijkstra for deadlock avoidance. It tests for safety by simulating the allocation of predetermined maximum possible amounts of all resources, and then makes an s-state check to see if all processes can eventually terminate safely. It is conservative and rarely used in general OS kernels because maximum resource requirements must be stated upfront.

3. Virtual Memory & Paging:
Virtual memory decouples the programmer's view of memory from physical RAM. The memory management unit (MMU) uses page tables and the Translation Lookaside Buffer (TLB) to translate virtual page numbers to physical page frame numbers. Page faults occur when an addressed page is not currently resident in physical memory.
"""
        if not existing_doc:
            settings.DOCUMENT_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
            syllabus_file = settings.DOCUMENT_STORAGE_PATH / "CS301_Module4.txt"
            syllabus_file.write_text(syllabus_text.strip(), encoding="utf-8")

            doc = Document(
                subject_id=subject.id,
                filename="CS301_Module4_Deadlocks_Paging.txt",
                file_type="txt",
                file_size_bytes=len(syllabus_text.encode("utf-8")),
                file_path=str(syllabus_file),
                ingestion_status=IngestionStatus.COMPLETED,
                chunk_count=3,
            )
            db.add(doc)
            await db.flush()
            await db.refresh(doc)

            # Ingest into ChromaDB RAG store
            rag_store = get_rag_store()
            chunk_count = await rag_store.ingest_document(
                subject_id=subject.id,
                document_id=doc.id,
                file_path=syllabus_file,
                filename=doc.filename,
            )
            doc.chunk_count = chunk_count
            print(f"  [+] Syllabus ingested into ChromaDB ({chunk_count} grounded chunks).")
        else:
            print("  [*] Syllabus already ingested.")

        # 4. Seed Viva Sessions
        print("\n[4/5] Seeding Viva Voce Examination Sessions...")

        # Session 1: Authentic Student (Alex Lovelace)
        sess1_stmt = select(VivaSession).where(VivaSession.student_id == student_alex.id)
        sess1 = (await db.execute(sess1_stmt)).scalar_one_or_none()

        if not sess1:
            sess1 = VivaSession(
                student_id=student_alex.id,
                subject_id=subject.id,
                status=SessionStatus.COMPLETED,
                recording_consent=True,
                total_score=8.8,
                overall_authenticity_likelihood=AuthenticityLikelihood.LOW,
                overall_authenticity_confidence=0.92,
                overall_authenticity_reasons=[
                    "Natural conversational disfluency rate (3.2 fillers/100 words)",
                    "Original explanatory analogies with low textbook n-gram overlap (14%)",
                    "Expressive cadence and pause distribution aligned with cognitive thinking",
                ],
                teacher_notes="Excellent command of concepts. Clearly explained why Banker's algorithm isn't used in Linux.",
                final_report={"verdict": "authentic_mastery"},
            )
            db.add(sess1)
            await db.flush()
            await db.refresh(sess1)

            # Audio directory
            sess1_dir = settings.AUDIO_STORAGE_PATH / sess1.id
            sess1_dir.mkdir(parents=True, exist_ok=True)

            # Turns for Alex
            turns_alex = [
                Turn(
                    session_id=sess1.id,
                    turn_number=1,
                    question_type="warmup",
                    topic="Course Introduction",
                    question_text="Welcome Alex. Could you introduce yourself and tell me what area of operating systems you enjoyed studying most?",
                    transcript="Hi, my name is Alex. I really enjoyed learning about concurrency and process synchronization, especially deadlocks and how threads coordinate.",
                    word_timestamps=[{"word": "Hi,", "start": 0.5, "end": 0.8}, {"word": "my", "start": 0.8, "end": 1.0}, {"word": "name", "start": 1.0, "end": 1.2}, {"word": "is", "start": 1.2, "end": 1.3}, {"word": "Alex.", "start": 1.3, "end": 1.7}],
                    audio_duration_seconds=5.2,
                    score_0_10=9.0,
                    rubric_breakdown={"correctness": 9.0, "completeness": 9.0, "clarity": 9.5, "depth": 8.5},
                    feedback="Polite, clear conversational baseline established.",
                    authenticity_likelihood=AuthenticityLikelihood.LOW,
                    authenticity_confidence=0.95,
                    authenticity_reasons=["Baseline natural cadence established."],
                ),
                Turn(
                    session_id=sess1.id,
                    turn_number=2,
                    question_type="conceptual",
                    topic="Coffman Conditions",
                    question_text="What are Coffman's four conditions for deadlock?",
                    transcript="Well, so the four conditions are, um, mutual exclusion, meaning only one thread can access a resource. Then hold and wait, where a thread holds a lock while waiting for another. No preemption, and, uh, circular wait.",
                    word_timestamps=[{"word": "Well,", "start": 1.1, "end": 1.4}, {"word": "so", "start": 1.5, "end": 1.7}, {"word": "the", "start": 1.7, "end": 1.9}],
                    audio_duration_seconds=11.4,
                    score_0_10=8.8,
                    rubric_breakdown={"correctness": 9.0, "completeness": 8.5, "clarity": 9.0, "depth": 8.5},
                    feedback="Accurate identification of all four conditions with spontaneous explanations.",
                    authenticity_likelihood=AuthenticityLikelihood.LOW,
                    authenticity_confidence=0.91,
                    authenticity_reasons=["Conversational formulation pauses and natural paraphrasing."],
                ),
                Turn(
                    session_id=sess1.id,
                    turn_number=3,
                    question_type="probe",
                    topic="Banker's Algorithm",
                    question_text="In your own everyday words, why is Banker's algorithm not typically used in the Linux kernel?",
                    transcript="Because, honestly, it assumes processes know their maximum resource needs in advance. But in modern systems, applications allocate memory dynamically, so asking for maximums upfront is totally unrealistic.",
                    word_timestamps=[{"word": "Because,", "start": 0.9, "end": 1.3}],
                    audio_duration_seconds=9.8,
                    score_0_10=8.6,
                    rubric_breakdown={"correctness": 8.5, "completeness": 8.5, "clarity": 9.0, "depth": 8.5},
                    feedback="Insightful grasp of practical systems architecture vs theoretical models.",
                    authenticity_likelihood=AuthenticityLikelihood.LOW,
                    authenticity_confidence=0.90,
                    authenticity_reasons=["Zero textbook verbatim overlap; genuine spontaneous reasoning."],
                ),
            ]

            for t in turns_alex:
                # Write dummy WAV
                wav_path = sess1_dir / f"{t.id}.wav"
                with open(wav_path, "wb") as f:
                    f.write(generate_dummy_wav(3.0))
                t.student_audio_path = str(wav_path)
                db.add(t)

            print(f"  [+] Seeded Authentic Viva Session: {student_alex.full_name} (Score: 8.8, Flag: LOW)")
        else:
            print(f"  [*] Existing Session for {student_alex.full_name}")

        # Session 2: Note-Reading Student (Robert Smith)
        sess2_stmt = select(VivaSession).where(VivaSession.student_id == student_robert.id)
        sess2 = (await db.execute(sess2_stmt)).scalar_one_or_none()

        if not sess2:
            sess2 = VivaSession(
                student_id=student_robert.id,
                subject_id=subject.id,
                status=SessionStatus.COMPLETED,
                recording_consent=True,
                total_score=6.2,
                overall_authenticity_likelihood=AuthenticityLikelihood.HIGH,
                overall_authenticity_confidence=0.86,
                overall_authenticity_reasons=[
                    "High 4-gram verbatim overlap with course syllabus (68%)",
                    "Unusually continuous flow without natural hesitations (0.2 fillers/100 words)",
                    "Mid-clause pause clustering suggestive of visual line-scanning",
                    "Score drop from 9.0 on textbook definitions to 3.5 on unexpected probe",
                ],
                teacher_notes="Recited textbook definitions perfectly, but was unable to explain how paging handles memory fragmentation when probed.",
                final_report={"verdict": "scripted_recitation_detected"},
            )
            db.add(sess2)
            await db.flush()
            await db.refresh(sess2)

            sess2_dir = settings.AUDIO_STORAGE_PATH / sess2.id
            sess2_dir.mkdir(parents=True, exist_ok=True)

            turns_robert = [
                Turn(
                    session_id=sess2.id,
                    turn_number=1,
                    question_type="conceptual",
                    topic="Coffman Conditions",
                    question_text="What are Coffman's four conditions for deadlock?",
                    transcript="A deadlock state occurs if and only if four necessary conditions hold simultaneously: Mutual Exclusion wherein at least one resource must be held in a non-shareable mode; Hold and Wait where a process must be currently holding at least one resource and requesting additional resources; No Preemption; Circular Wait.",
                    word_timestamps=[{"word": "A", "start": 0.2, "end": 0.4}, {"word": "deadlock", "start": 0.4, "end": 0.8}],
                    audio_duration_seconds=12.1,
                    score_0_10=9.0,
                    rubric_breakdown={"correctness": 9.5, "completeness": 9.5, "clarity": 8.5, "depth": 7.0},
                    feedback="Textbook definition accurate, but delivery shows reading pattern.",
                    authenticity_likelihood=AuthenticityLikelihood.HIGH,
                    authenticity_confidence=0.88,
                    authenticity_reasons=["High 4-gram overlap (72%) with course document.", "Zero natural disfluency markers."],
                ),
                Turn(
                    session_id=sess2.id,
                    turn_number=2,
                    question_type="probe",
                    topic="Deadlock Prevention Analogy",
                    question_text="Explain deadlock circular wait using a real-world analogy with cars at a four-way intersection.",
                    transcript="At a four-way intersection... uh... cars wait... I don't remember what the notes said about intersections.",
                    word_timestamps=[{"word": "At", "start": 3.5, "end": 3.9}],
                    audio_duration_seconds=8.0,
                    score_0_10=3.5,
                    rubric_breakdown={"correctness": 3.5, "completeness": 3.0, "clarity": 5.0, "depth": 2.5},
                    feedback="Candidate struggled significantly when asked to depart from written definitions.",
                    authenticity_likelihood=AuthenticityLikelihood.HIGH,
                    authenticity_confidence=0.85,
                    authenticity_reasons=["5.5 point score drop between memorized definition and probe question."],
                ),
            ]

            for t in turns_robert:
                wav_path = sess2_dir / f"{t.id}.wav"
                with open(wav_path, "wb") as f:
                    f.write(generate_dummy_wav(3.0))
                t.student_audio_path = str(wav_path)
                db.add(t)

            # Add sample teacher override & audit log for Robert
            override = ScoreOverride(
                session_id=sess2.id,
                turn_id=turns_robert[0].id,
                teacher_id=teacher.id,
                original_score=9.0,
                new_score=7.0,
                original_authenticity=AuthenticityLikelihood.HIGH.value,
                new_authenticity=AuthenticityLikelihood.MEDIUM.value,
                reason="Adjusted score down due to clear textbook recital without spontaneous explanation.",
            )
            audit = AuditLog(
                user_id=teacher.id,
                action="SCORE_OVERRIDE",
                entity_type="viva_session",
                entity_id=sess2.id,
                previous_state={"score": 9.0},
                new_state={"score": 7.0},
                reason="Teacher manual audit review.",
            )
            db.add(override)
            db.add(audit)

            print(f"  [+] Seeded Scripted Viva Session: {student_robert.full_name} (Score: 6.2, Flag: HIGH risk)")
        else:
            print(f"  [*] Existing Session for {student_robert.full_name}")

        await db.commit()

    print("\n[5/5] Database and Demo Assets Successfully Seeded! [*]")
    print("=" * 60)
    print("Ready to log in and demo:")
    print("  * Teacher Login: teacher@vivaiq.edu  / TeacherPass123!")
    print("  * Student Login: alex@student.edu     / StudentPass123!")
    print("  * Student Login: robert@student.edu   / StudentPass123!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(seed_demo())

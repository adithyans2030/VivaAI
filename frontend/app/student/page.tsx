"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, Subject, VivaSession, Turn } from "@/lib/api";
import AudioOrb, { ExaminerState } from "@/components/AudioOrb";
import MicCheckModal from "@/components/MicCheckModal";
import {
  BookOpen,
  Mic,
  RotateCcw,
  Sparkles,
  ArrowRight,
  ShieldAlert,
  Award,
  Layers,
  ChevronRight,
  HelpCircle,
  FileText,
} from "lucide-react";

export default function StudentVivaPage() {
  const router = useRouter();

  // Catalog & Session state
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [selectedSubject, setSelectedSubject] = useState<Subject | null>(null);
  const [session, setSession] = useState<VivaSession | null>(null);
  const [isMicModalOpen, setIsMicModalOpen] = useState(false);

  // Active examination state
  const [examinerState, setExaminerState] = useState<ExaminerState>("idle");
  const [currentTurnIndex, setCurrentTurnIndex] = useState(0);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [currentTranscript, setCurrentTranscript] = useState("");
  const [audioLevel, setAudioLevel] = useState(0);
  const [repeatedCount, setRepeatedCount] = useState(0);

  // Questions simulation script if offline/demo
  const sampleTurns: Partial<Turn>[] = [
    {
      turn_number: 1,
      question_type: "warmup",
      topic: "Course Overview",
      question_text: "Welcome to your viva voce examination. To begin, could you briefly introduce yourself and share which operating system topic you found most interesting during your study?",
      prompt_version: "v1.0",
    },
    {
      turn_number: 2,
      question_type: "conceptual",
      topic: "Deadlocks",
      question_text: "Let's discuss deadlocks. What are Coffman's four necessary conditions that must hold simultaneously for a deadlock to occur?",
      prompt_version: "v1.0",
    },
    {
      turn_number: 3,
      question_type: "application",
      topic: "Resource Allocation",
      question_text: "Suppose two concurrent processes both require a database lock and a disk write channel. If process A holds the lock and waits for the channel, while process B holds the channel and waits for the lock, what deadlock avoidance strategy would you employ?",
      prompt_version: "v1.0",
    },
    {
      turn_number: 4,
      question_type: "probe",
      topic: "Banker's Algorithm",
      question_text: "In your own words, without quoting textbook definitions, explain why the Banker's algorithm might be considered too conservative or impractical in modern high-throughput operating systems.",
      prompt_version: "v1.0",
    },
  ];

  // Load available subjects
  useEffect(() => {
    api.listSubjects()
      .then((data) => {
        setSubjects(data);
        if (data.length > 0) {
          setSelectedSubject(data[0]);
        }
      })
      .catch(() => {
        // Fallback for immediate UI presentation
        const mockSubject: Subject = {
          id: "cs301-demo",
          name: "Operating Systems & Concurrency",
          code: "CS301",
          description: "Process synchronization, deadlock conditions, resource graphs, and memory management.",
          teacher_id: "teacher-1",
          document_count: 3,
        };
        setSubjects([mockSubject]);
        setSelectedSubject(mockSubject);
      });
  }, []);

  // Text-To-Speech function
  const speakQuestion = (text: string, onEnd?: () => void) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      if (onEnd) onEnd();
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.95; // Calm, deliberate examiner pace
    utterance.pitch = 1.0;

    setExaminerState("examiner_speaking");

    utterance.onend = () => {
      setExaminerState("listening");
      startListening();
      if (onEnd) onEnd();
    };

    utterance.onerror = () => {
      setExaminerState("listening");
      startListening();
      if (onEnd) onEnd();
    };

    window.speechSynthesis.speak(utterance);
  };

  // Speech Recognition / Voice Input
  const recognitionRef = useRef<any>(null);

  const startListening = () => {
    setCurrentTranscript("");
    if (typeof window === "undefined") return;

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (SpeechRecognition) {
      try {
        const recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = "en-US";

        recognition.onresult = (event: any) => {
          let interim = "";
          let final = "";
          for (let i = 0; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
              final += event.results[i][0].transcript;
            } else {
              interim += event.results[i][0].transcript;
            }
          }
          setCurrentTranscript(final || interim);
          setAudioLevel(0.4 + Math.random() * 0.5);
        };

        recognition.onerror = () => {
          setAudioLevel(0.1);
        };

        recognition.start();
        recognitionRef.current = recognition;
      } catch (err) {
        console.error("Speech recognition error", err);
      }
    } else {
      // Audio level mock generator for browser unsupported speech recognition
      const interval = setInterval(() => {
        setAudioLevel(0.3 + Math.random() * 0.5);
      }, 150);
      return () => clearInterval(interval);
    }
  };

  const stopListening = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }
    setAudioLevel(0);
  };

  // Start Exam Flow
  const handleProceedAfterConsent = async () => {
    setIsMicModalOpen(false);
    if (!selectedSubject) return;

    try {
      const sess = await api.createSession(selectedSubject.id);
      await api.recordConsent(sess.id, true);
      setSession(sess);
    } catch {
      // Mock session for UI
      const mockSess: VivaSession = {
        id: "viva-sess-1",
        student_id: "student-1",
        subject_id: selectedSubject.id,
        status: "in_progress",
        recording_consent: true,
        overall_authenticity_likelihood: "unknown",
        created_at: new Date().toISOString(),
      };
      setSession(mockSess);
    }

    // Launch Question 1
    launchTurn(0);
  };

  const launchTurn = (index: number) => {
    if (index >= sampleTurns.length) {
      setExaminerState("completed");
      return;
    }

    setCurrentTurnIndex(index);
    setRepeatedCount(0);
    const turnData = sampleTurns[index];
    speakQuestion(turnData.question_text || "");
  };

  // Submit Answer
  const handleSubmitAnswer = () => {
    stopListening();
    setExaminerState("processing");

    const answer = currentTranscript.trim() || "The four conditions are Mutual Exclusion, Hold and Wait, No Preemption, and Circular Wait.";

    // Simulate server grading & authenticity processing
    setTimeout(() => {
      const mockRubric = {
        correctness: 8.5,
        completeness: 8.0,
        clarity: 9.0,
        depth: 7.5,
      };

      const completedTurn: Turn = {
        id: `turn-${currentTurnIndex + 1}`,
        turn_number: currentTurnIndex + 1,
        question_text: sampleTurns[currentTurnIndex].question_text || "",
        question_type: sampleTurns[currentTurnIndex].question_type || "conceptual",
        topic: sampleTurns[currentTurnIndex].topic || "General",
        transcript: answer,
        score_0_10: currentTurnIndex === 0 ? 9.0 : 8.2,
        rubric_breakdown: mockRubric,
        feedback: "Sound foundational understanding demonstrated with clear articulation.",
        authenticity_likelihood: currentTurnIndex === 3 ? "low" : "low",
        authenticity_confidence: 0.88,
        authenticity_reasons: [
          "Conversational pause frequency consistent with spontaneous reasoning",
          "Low n-gram verbatim overlap with textbook reference chunks",
          "Natural prosodic pitch variability across clauses",
        ],
      };

      setTurns((prev) => [...prev, completedTurn]);

      if (currentTurnIndex + 1 < sampleTurns.length) {
        launchTurn(currentTurnIndex + 1);
      } else {
        setExaminerState("completed");
      }
    }, 2200);
  };

  // Repeat question
  const handleRepeatQuestion = () => {
    if (repeatedCount >= 1) return;
    setRepeatedCount((c) => c + 1);
    stopListening();
    speakQuestion(sampleTurns[currentTurnIndex]?.question_text || "");
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      {/* Subject selection screen if no active session */}
      {!session ? (
        <div className="max-w-3xl mx-auto space-y-6">
          <div className="text-center space-y-2">
            <span className="text-xs font-semibold uppercase tracking-wider px-2.5 py-1 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              Examination Room
            </span>
            <h1 className="text-3xl font-bold text-white tracking-tight">Select Subject for Viva Voce</h1>
            <p className="text-sm text-slate-400">
              The AI examiner will ask questions grounded in your course material and evaluate your spoken answers.
            </p>
          </div>

          <div className="grid gap-4 mt-6">
            {subjects.map((subj) => (
              <div
                key={subj.id}
                onClick={() => setSelectedSubject(subj)}
                className={`p-5 rounded-2xl border transition-all cursor-pointer ${
                  selectedSubject?.id === subj.id
                    ? "bg-indigo-950/40 border-indigo-500 shadow-lg shadow-indigo-500/10"
                    : "glass-panel border-slate-800 hover:border-slate-700 hover:bg-slate-900/60"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 font-bold text-sm">
                      {subj.code}
                    </div>
                    <div>
                      <h3 className="text-base font-semibold text-white">{subj.name}</h3>
                      <p className="text-xs text-slate-400 line-clamp-1">{subj.description}</p>
                    </div>
                  </div>
                  <ChevronRight className="w-5 h-5 text-slate-500" />
                </div>
              </div>
            ))}
          </div>

          <div className="flex justify-end pt-4">
            <button
              onClick={() => setIsMicModalOpen(true)}
              disabled={!selectedSubject}
              className="flex items-center gap-2 px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm shadow-xl shadow-indigo-500/25 transition-all cursor-pointer disabled:opacity-50"
            >
              <Mic className="w-4 h-4" />
              Begin Microphone Check & Consent
            </button>
          </div>
        </div>
      ) : (
        /* Active Viva Room */
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Main Focus Area (Audio Orb & Current Question) */}
          <div className="lg:col-span-8 space-y-6">
            {/* Top Progress Bar */}
            <div className="glass-panel p-4 rounded-2xl border border-slate-800 flex items-center justify-between">
              <div>
                <span className="text-[11px] font-semibold text-indigo-400 uppercase tracking-wider">
                  {selectedSubject?.code} • {selectedSubject?.name}
                </span>
                <div className="text-xs text-slate-400 mt-0.5">
                  Question {currentTurnIndex + 1} of {sampleTurns.length}
                </div>
              </div>

              {/* Badges */}
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700 capitalize">
                  {sampleTurns[currentTurnIndex]?.question_type} Question
                </span>
                {repeatedCount === 0 && examinerState === "listening" && (
                  <button
                    onClick={handleRepeatQuestion}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-800/80 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors"
                  >
                    <RotateCcw className="w-3 h-3" />
                    Repeat Question
                  </button>
                )}
              </div>
            </div>

            {/* Central Examiner Orb Container */}
            <div className="glass-panel p-8 rounded-3xl border border-slate-800/80 flex flex-col items-center justify-center min-h-[380px] relative overflow-hidden">
              <AudioOrb state={examinerState} audioLevel={audioLevel} />

              {/* Active Spoken Question Card */}
              {examinerState !== "idle" && (
                <div className="mt-4 p-5 rounded-2xl bg-slate-900/90 border border-slate-700/80 max-w-xl text-center space-y-2 shadow-xl animate-in fade-in duration-300">
                  <div className="text-[11px] font-semibold text-indigo-400 uppercase tracking-wider flex items-center justify-center gap-1">
                    <Sparkles className="w-3 h-3" />
                    Examiner Question ({sampleTurns[currentTurnIndex]?.topic})
                  </div>
                  <p className="text-sm font-medium text-slate-100 leading-relaxed">
                    "{sampleTurns[currentTurnIndex]?.question_text}"
                  </p>
                </div>
              )}
            </div>

            {/* Live Student Response & Transcript Bar */}
            {examinerState === "listening" && (
              <div className="glass-panel p-5 rounded-2xl border border-emerald-500/30 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs font-semibold text-emerald-400">
                    <Mic className="w-4 h-4 animate-pulse" />
                    Live Captions (Speaking in Your Own Words)
                  </div>
                  <span className="text-[11px] text-slate-400">Speak clearly into microphone</span>
                </div>

                <div className="min-h-[50px] p-3 rounded-xl bg-slate-950/80 border border-slate-800 text-sm text-slate-200 italic">
                  {currentTranscript ? `"${currentTranscript}"` : "Waiting for your spoken answer..."}
                </div>

                <div className="flex justify-end gap-2 pt-1">
                  <button
                    onClick={handleSubmitAnswer}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs shadow-lg shadow-emerald-500/25 transition-all cursor-pointer"
                  >
                    Finish & Submit Answer
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Right Sidebar: Turns History & Rubric Feedback */}
          <div className="lg:col-span-4 space-y-4">
            <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-4">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Layers className="w-4 h-4 text-indigo-400" />
                Viva Turn Progress
              </h3>

              <div className="space-y-3 max-h-[550px] overflow-y-auto pr-1">
                {turns.length === 0 ? (
                  <div className="text-center py-10 text-xs text-slate-500">
                    Graded answers and rubric breakdowns will appear here after each turn.
                  </div>
                ) : (
                  turns.map((t) => (
                    <div
                      key={t.id}
                      className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2.5"
                    >
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-slate-200">
                          Turn #{t.turn_number}: {t.topic}
                        </span>
                        <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-bold border border-emerald-500/20">
                          {t.score_0_10}/10
                        </span>
                      </div>

                      <p className="text-xs text-slate-400 italic line-clamp-2">
                        "{t.transcript}"
                      </p>

                      {/* Rubric scores */}
                      {t.rubric_breakdown && (
                        <div className="grid grid-cols-2 gap-1.5 text-[10px] bg-slate-950/60 p-2 rounded-lg text-slate-300">
                          <div>Correctness: <span className="font-semibold text-indigo-300">{t.rubric_breakdown.correctness}</span></div>
                          <div>Completeness: <span className="font-semibold text-indigo-300">{t.rubric_breakdown.completeness}</span></div>
                          <div>Clarity: <span className="font-semibold text-indigo-300">{t.rubric_breakdown.clarity}</span></div>
                          <div>Depth: <span className="font-semibold text-indigo-300">{t.rubric_breakdown.depth}</span></div>
                        </div>
                      )}

                      <div className="text-[11px] text-slate-400 border-t border-slate-800/80 pt-1.5">
                        <span className="text-indigo-400 font-medium">Feedback: </span>
                        {t.feedback}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Mic Check & Consent Modal */}
      <MicCheckModal
        isOpen={isMicModalOpen}
        onConsentAndProceed={handleProceedAfterConsent}
        onCancel={() => setIsMicModalOpen(false)}
        subjectName={selectedSubject?.name || "Viva Examination"}
      />
    </div>
  );
}

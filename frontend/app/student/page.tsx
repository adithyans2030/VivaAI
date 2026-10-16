"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, Subject, VivaSession, Turn } from "@/lib/api";
import { VivaWebSocketClient } from "@/lib/ws";
import { AudioStreamRecorder } from "@/lib/audio-recorder";
import AudioOrb, { ExaminerState } from "@/components/AudioOrb";
import MicCheckModal from "@/components/MicCheckModal";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import {
  BookOpen,
  Mic,
  RotateCcw,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  Layers,
  ChevronRight,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
} from "lucide-react";

export default function StudentVivaPage() {
  const router = useRouter();

  // Catalog & Session state
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [selectedSubject, setSelectedSubject] = useState<Subject | null>(null);
  const [session, setSession] = useState<VivaSession | null>(null);
  const [isMicModalOpen, setIsMicModalOpen] = useState(false);
  const [isInitializing, setIsInitializing] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [liveError, setLiveError] = useState<string | null>(null);

  // Active examination state
  const [examinerState, setExaminerState] = useState<ExaminerState>("idle");
  const [currentTurnIndex, setCurrentTurnIndex] = useState(0);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [currentTranscript, setCurrentTranscript] = useState("");
  const [audioLevel, setAudioLevel] = useState(0);
  const [repeatedCount, setRepeatedCount] = useState(0);
  const [currentQuestion, setCurrentQuestion] = useState<{
    turn_id: string;
    turn_number: number;
    question_text: string;
    topic?: string;
    question_type?: string;
  } | null>(null);

  const isDemoMode = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

  // Load available subjects from backend
  const loadSubjects = async () => {
    setFetchError(null);
    try {
      const data = await api.listSubjects();
      setSubjects(data);
      if (data.length > 0) {
        setSelectedSubject(data[0]);
      }
    } catch (err: any) {
      if (isDemoMode) {
        const demoSubject: Subject = {
          id: "demo-course",
          name: "Computer Science Viva (Demo)",
          code: "CS101",
          description: "Demo course material available in offline simulation mode.",
          teacher_id: "teacher-1",
          document_count: 1,
        };
        setSubjects([demoSubject]);
        setSelectedSubject(demoSubject);
      } else {
        setFetchError(err.message || "Unable to connect to VivaIQ server. Please ensure the backend is running.");
      }
    }
  };

  useEffect(() => {
    loadSubjects();
  }, []);

  // Text-To-Speech function
  const speakQuestion = (text: string, onEnd?: () => void) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      setExaminerState("listening");
      startListening();
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

  // WebSocket & Audio Recorder references
  const wsClientRef = useRef<VivaWebSocketClient | null>(null);
  const recorderRef = useRef<AudioStreamRecorder | null>(null);
  const recognitionRef = useRef<any>(null);

  const startListening = () => {
    setCurrentTranscript("");
    if (typeof window === "undefined") return;

    try {
      const recorder = new AudioStreamRecorder({
        onAudioChunk: (chunkB64, chunkIndex) => {
          if (currentQuestion?.turn_id) {
            wsClientRef.current?.sendAudioChunk(currentQuestion.turn_id, chunkIndex, chunkB64);
          }
        },
        onVolumeChange: (vol) => {
          setAudioLevel(vol);
        },
        onSpeechEnd: () => {
          handleSubmitAnswer();
        },
      });
      recorder.start().catch((err) => console.warn("AudioStreamRecorder mic error:", err));
      recorderRef.current = recorder;
    } catch (e) {
      console.warn("Could not start audio stream recorder:", e);
    }

    // Client-side web speech recognition for live speech captions
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
        };

        recognition.onerror = () => {};
        recognition.start();
        recognitionRef.current = recognition;
      } catch (err) {
        console.error("Speech recognition error", err);
      }
    }
  };

  const stopListening = () => {
    if (recorderRef.current) {
      recorderRef.current.stop();
      recorderRef.current = null;
    }
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }
    setAudioLevel(0);
  };

  // Start Real Exam Flow
  const handleProceedAfterConsent = async () => {
    setIsMicModalOpen(false);
    if (!selectedSubject) return;

    setLiveError(null);
    setIsInitializing(true);

    try {
      // 1. Create real session on backend
      const sess = await api.createSession(selectedSubject.id);
      // 2. Record explicit student recording consent
      await api.recordConsent(sess.id, true);
      setSession(sess);

      // 3. Obtain short-lived, single-use WebSocket ticket (WS-2.3)
      const ticket = await api.getWsTicket(sess.id);

      // 4. Connect WebSocket with ticket
      const ws = new VivaWebSocketClient(sess.id, ticket, {
        onOpen: () => {
          setIsInitializing(false);
          ws.sendReady();
        },
        onQuestion: (q) => {
          setCurrentQuestion(q);
          setCurrentTurnIndex(q.turn_number - 1);
          setRepeatedCount(0);
          speakQuestion(q.question_text);
        },
        onTranscript: (text) => {
          if (text) setCurrentTranscript(text);
        },
        onFeedback: (fb) => {
          const completedTurn: Turn = {
            id: fb.turn_id,
            turn_number: currentTurnIndex + 1,
            question_text: currentQuestion?.question_text || "",
            question_type: currentQuestion?.question_type || "conceptual",
            topic: currentQuestion?.topic || "Topic",
            transcript: currentTranscript.trim(),
            score_0_10: fb.score_0_10,
            rubric_breakdown: fb.rubric,
            feedback: fb.feedback,
            authenticity_likelihood: fb.authenticity?.likelihood || "low",
            authenticity_confidence: fb.authenticity?.confidence || 0.9,
            authenticity_reasons: fb.authenticity?.reasons || [],
          };
          setTurns((prev) => [...prev, completedTurn]);
        },
        onSessionComplete: () => {
          setExaminerState("completed");
        },
        onStateChange: (st) => {
          if (
            st === "processing" ||
            st === "examiner_speaking" ||
            st === "listening" ||
            st === "completed"
          ) {
            setExaminerState(st as any);
          }
        },
        onError: (err) => {
          setLiveError(err.message || "An error occurred during examination.");
        },
      });

      ws.connect();
      wsClientRef.current = ws;
    } catch (err: any) {
      setIsInitializing(false);
      setLiveError(err.message || "Failed to start viva session. Please check connection and retry.");
    }
  };

  // Submit Answer to Real Backend
  const handleSubmitAnswer = () => {
    stopListening();
    setExaminerState("processing");

    if (currentQuestion?.turn_id) {
      wsClientRef.current?.sendSpeechEnd(currentQuestion.turn_id);
    }
    // The UI remains in 'processing' state while the real backend transcribes & grades.
    // No fake timers or fabricated results (WS-3).
  };

  // Repeat question (at most 1 repeat permitted per turn)
  const handleRepeatQuestion = () => {
    if (repeatedCount >= 1 || !currentQuestion) return;
    setRepeatedCount((c) => c + 1);
    stopListening();
    wsClientRef.current?.sendRepeatQuestion(currentQuestion.turn_id);
    speakQuestion(currentQuestion.question_text);
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8 text-[var(--text-primary)]">
      {/* Persistent Demo Mode Banner if explicitly active */}
      {isDemoMode && (
        <div className="p-2.5 rounded-xl text-center text-xs bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/20">
          Demo mode: results are simulated for offline presentation.
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* Subject Selection View                                        */}
      {/* ------------------------------------------------------------- */}
      {!session ? (
        <div className="max-w-3xl mx-auto space-y-8 py-6">
          <div className="text-center space-y-3">
            <div className="flex items-center justify-center gap-2">
              <span className="w-5 h-[1.5px] bg-[var(--text-secondary)]" />
              <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-secondary)]">
                Examination Room
              </span>
            </div>
            <h1 className="font-editorial text-4xl sm:text-5xl font-normal tracking-tight">
              Select Your Examination Subject
            </h1>
            <p className="text-sm text-[var(--text-secondary)] max-w-lg mx-auto leading-relaxed">
              Examinations are strictly grounded in course textbooks, syllabus notes, and lecture materials uploaded by your professors.
            </p>
          </div>

          {/* Connection Error Banner */}
          {fetchError ? (
            <div className="p-6 rounded-2xl bg-[var(--error-bg)] border border-[var(--error-border)] space-y-3 text-center">
              <div className="flex items-center justify-center gap-2 text-[var(--error-text)] font-semibold text-sm">
                <AlertCircle className="w-5 h-5" />
                Connection Unavailable
              </div>
              <p className="text-xs text-[var(--text-secondary)] max-w-md mx-auto">{fetchError}</p>
              <Button size="sm" variant="outline" onClick={loadSubjects} className="mt-2">
                <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
                Retry Connection
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {subjects.map((subj) => {
                  const isSelected = selectedSubject?.id === subj.id;
                  return (
                    <div
                      key={subj.id}
                      onClick={() => setSelectedSubject(subj)}
                      className={`p-5 rounded-2xl border transition-all cursor-pointer text-left space-y-2.5 ${
                        isSelected
                          ? "bg-[var(--bg-card)] border-[var(--border-focus)] shadow-sm ring-1 ring-[var(--border-focus)]"
                          : "bg-[var(--bg-card)] border-[var(--border-default)] hover:border-[var(--border-focus)] hover:bg-[var(--bg-card-subtle)]"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--accent-primary)] font-mono">
                          {subj.code}
                        </span>
                        {isSelected && <span className="w-2 h-2 rounded-full bg-[var(--accent-primary)]" />}
                      </div>

                      <h3 className="font-editorial text-xl font-normal leading-snug">{subj.name}</h3>

                      <p className="text-xs text-[var(--text-secondary)] line-clamp-2 leading-relaxed">
                        {subj.description}
                      </p>

                      <div className="pt-2 flex items-center justify-between text-[11px] text-[var(--text-muted)] border-t border-[var(--border-default)]">
                        <span>{subj.document_count || 1} course document(s)</span>
                        <ChevronRight className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                      </div>
                    </div>
                  );
                })}
              </div>

              {subjects.length > 0 && (
                <div className="flex justify-center pt-4">
                  <Button
                    size="lg"
                    onClick={() => setIsMicModalOpen(true)}
                    disabled={!selectedSubject || isInitializing}
                    className="min-w-[260px]"
                  >
                    <Mic className="w-4 h-4 mr-2" />
                    Enter Viva Room
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                </div>
              )}
            </div>
          )}

          {/* Ethical Guardrail Disclaimer */}
          <div className="flex items-center justify-center gap-2 text-xs text-[var(--text-secondary)] pt-4 text-center">
            <ShieldCheck className="w-4 h-4 text-[var(--accent-primary)] shrink-0" />
            <span>
              Your assessment supports a conversation. It is advisory only, never a cheating detector or a final judgement.
            </span>
          </div>
        </div>
      ) : (
        /* ------------------------------------------------------------- */
        /* Active Viva Examination Room                                  */
        /* ------------------------------------------------------------- */
        <div className="space-y-6">
          {/* Top Status Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)]">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)] flex items-center justify-center text-[var(--accent-primary)]">
                <BookOpen className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-semibold">{selectedSubject?.name}</h3>
                <div className="text-[11px] text-[var(--text-muted)]">
                  Live Examination • Turn {currentTurnIndex + 1}
                </div>
              </div>
            </div>

            <Badge variant="advisory">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              Advisory Evaluation Engine Active
            </Badge>
          </div>

          {/* Live Error Notification */}
          {liveError && (
            <div className="p-4 rounded-xl bg-[var(--error-bg)] border border-[var(--error-border)] flex items-center justify-between text-xs text-[var(--error-text)]">
              <span>{liveError}</span>
              <Button size="sm" variant="ghost" onClick={() => setLiveError(null)}>
                Dismiss
              </Button>
            </div>
          )}

          {/* Main Visual Arena & Spoken Output */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
            {/* Visual Centerpiece (AudioOrb) */}
            <div className="lg:col-span-6 flex flex-col items-center justify-center p-8 rounded-3xl bg-[var(--bg-card)] border border-[var(--border-default)] min-h-[380px] space-y-6">
              <AudioOrb state={examinerState} audioLevel={audioLevel} />

              <div className="text-center space-y-1">
                <div className="text-xs font-semibold uppercase tracking-wider text-[var(--accent-primary)]">
                  {examinerState === "examiner_speaking" && "Examiner Asking Question"}
                  {examinerState === "listening" && "Listening to Your Answer"}
                  {examinerState === "processing" && "Evaluating Rubric & Evidence"}
                  {examinerState === "completed" && "Viva Examination Complete"}
                </div>
                <div className="text-[11px] text-[var(--text-muted)]">
                  {examinerState === "listening" && "Speak clearly into your microphone"}
                  {examinerState === "processing" && "Analyzing answer grounding and prosodic dynamics..."}
                </div>
              </div>
            </div>

            {/* Question Card & Live Speech Output */}
            <div className="lg:col-span-6 space-y-4">
              <div className="p-6 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] shadow-xs space-y-4">
                <div className="flex items-center justify-between">
                  <Badge variant="eyebrow">
                    Question #{currentTurnIndex + 1} • {currentQuestion?.topic || "Topic"}
                  </Badge>
                  <button
                    onClick={handleRepeatQuestion}
                    disabled={repeatedCount >= 1 || examinerState !== "listening"}
                    className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    Repeat Question ({1 - repeatedCount} left)
                  </button>
                </div>

                <div className="font-editorial text-xl sm:text-2xl font-normal leading-relaxed text-[var(--text-primary)]">
                  "{currentQuestion?.question_text || "Preparing your next grounded question..."}"
                </div>

                {/* Candidate Live Transcription Output */}
                <div className="p-4 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)] space-y-2">
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] flex items-center justify-between">
                    <span>Your Spoken Answer:</span>
                    {examinerState === "listening" && (
                      <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                        Listening
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] italic min-h-[44px]">
                    {currentTranscript ? `"${currentTranscript}"` : "(Awaiting speech input...)"}
                  </p>
                </div>

                {/* Control Actions */}
                <div className="flex items-center justify-between pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      if (wsClientRef.current) wsClientRef.current.sendEndSession();
                      setExaminerState("completed");
                    }}
                  >
                    End Session
                  </Button>

                  {examinerState === "listening" && (
                    <Button size="sm" onClick={handleSubmitAnswer}>
                      Submit Answer
                      <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Turn Progression History */}
          {turns.length > 0 && (
            <div className="p-6 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] shadow-xs space-y-4">
              <h3 className="font-editorial text-lg font-normal">Completed Turn Feedback</h3>
              <div className="space-y-3">
                {turns.map((t, i) => (
                  <div
                    key={i}
                    className="p-4 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)] space-y-2"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-[var(--text-primary)]">
                        Turn #{t.turn_number}: {t.topic}
                      </span>
                      <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                        {t.score_0_10}/10
                      </span>
                    </div>
                    <p className="text-xs text-[var(--text-secondary)] italic">"{t.transcript}"</p>
                    <p className="text-xs text-[var(--text-muted)]">{t.feedback}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Microphone Check Modal */}
      <MicCheckModal
        isOpen={isMicModalOpen}
        onCancel={() => setIsMicModalOpen(false)}
        onConsentAndProceed={handleProceedAfterConsent}
        subjectName={selectedSubject?.name || "Viva Voce"}
      />
    </div>
  );
}

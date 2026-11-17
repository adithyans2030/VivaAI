"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, Subject, VivaSession, Turn } from "@/lib/api";
import { QuestionPayload, VivaWebSocketClient } from "@/lib/ws";
import { AudioStreamRecorder } from "@/lib/audio-recorder";
import AudioOrb, { ExaminerState } from "@/components/AudioOrb";
import MicCheckModal from "@/components/MicCheckModal";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import {
  BookOpen,
  Mic,
  RotateCcw,
  ArrowRight,
  ShieldCheck,
  ChevronRight,
  AlertCircle,
  RefreshCw,
} from "lucide-react";

// Minimal Web Speech API typings (not yet in lib.dom). Used only for live captions;
// the authoritative transcript comes from server-side Whisper.
interface CaptionRecognitionEvent {
  results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>;
}
interface CaptionRecognition {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: CaptionRecognitionEvent) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}
type SpeechWindow = Window & {
  SpeechRecognition?: new () => CaptionRecognition;
  webkitSpeechRecognition?: new () => CaptionRecognition;
};

const errorMessage = (err: unknown, fallback: string) => (err instanceof Error && err.message) || fallback;

// Server errors after which the same question is still open and the student should simply answer again.
const RETRY_ANSWER_CODES = new Set(["EMPTY_AUDIO", "STT_FAILED"]);
// Caption errors that just mean "nothing heard yet"; anything else means captions cannot work here.
const BENIGN_CAPTION_ERRORS = new Set(["no-speech", "aborted"]);
const SLOW_EVALUATION_SECONDS = 20;

/** Elapsed-time readout so a slow transcription never looks like a frozen page. */
function EvaluationTimer({ since }: { since: number }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const seconds = Math.max(0, Math.floor((now - since) / 1000));
  return (
    <span>
      Transcribing and grading your answer… {seconds}s
      {seconds >= SLOW_EVALUATION_SECONDS && (
        <span className="block mt-1 text-amber-600 dark:text-amber-400">
          This is taking longer than usual. The server may be busy; please keep this page open.
        </span>
      )}
    </span>
  );
}

export default function StudentVivaPage() {
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
  const [currentQuestion, setCurrentQuestion] = useState<QuestionPayload | null>(null);
  const [evaluatingSince, setEvaluatingSince] = useState<number | null>(null);
  const [captionsNote, setCaptionsNote] = useState<string | null>(null);

  // WebSocket callbacks live for the whole session, so they read these refs rather than
  // render-time state (which would be frozen at the moment the socket was created).
  const wsClientRef = useRef<VivaWebSocketClient | null>(null);
  const recorderRef = useRef<AudioStreamRecorder | null>(null);
  const recognitionRef = useRef<CaptionRecognition | null>(null);
  const playbackRef = useRef<HTMLAudioElement | null>(null);
  // Held so Chrome cannot garbage-collect the utterance mid-sentence (which silently drops `onend`).
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const speechWatchdogRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // True once the mic has opened for the question currently being asked; a late `onend` must not reopen it.
  const listenedForQuestionRef = useRef(false);
  const questionRef = useRef<QuestionPayload | null>(null);
  const transcriptRef = useRef("");
  // Identifies the recording whose chunks may still be sent. Bumping it discards an in-flight
  // recording (repeat, new question) so its tail cannot leak into the next answer.
  const recordingIdRef = useRef(0);

  const updateTranscript = (text: string) => {
    transcriptRef.current = text;
    setCurrentTranscript(text);
  };

  const loadSubjects = useCallback(async () => {
    setFetchError(null);
    try {
      const data = await api.listSubjects();
      setSubjects(data);
      if (data.length > 0) {
        setSelectedSubject(data[0]);
      }
    } catch (err) {
      setFetchError(errorMessage(err, "Unable to connect to VivaIQ server. Please ensure the backend is running."));
    }
  }, []);

  useEffect(() => {
    // Fetch on mount; state updates happen after the request resolves.
    const timer = setTimeout(() => void loadSubjects(), 0);
    return () => {
      clearTimeout(timer);
      wsClientRef.current?.disconnect();
      void recorderRef.current?.stop();
      recognitionRef.current?.stop();
      playbackRef.current?.pause();
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
      if (speechWatchdogRef.current) clearTimeout(speechWatchdogRef.current);
    };
  }, [loadSubjects]);

  const stopListening = async () => {
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    const recorder = recorderRef.current;
    recorderRef.current = null;
    setAudioLevel(0);
    return recorder ? recorder.stop() : undefined;
  };

  /** Stop the mic and throw the recording away instead of submitting it. */
  const abandonListening = () => {
    recordingIdRef.current++;
    void stopListening();
  };

  // Send speech_end only after the recorder has flushed its final chunk.
  const submitAnswer = async (durationMs?: number) => {
    const question = questionRef.current;
    setExaminerState("processing");
    setEvaluatingSince(Date.now());
    const measured = await stopListening();
    if (question) {
      wsClientRef.current?.sendSpeechEnd(question.turn_id, durationMs ?? measured);
    }
  };

  const startListening = () => {
    if (speechWatchdogRef.current) clearTimeout(speechWatchdogRef.current);
    speechWatchdogRef.current = null;
    if (listenedForQuestionRef.current) return; // already listened (or answered) for this question
    listenedForQuestionRef.current = true;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    playbackRef.current?.pause();
    updateTranscript("");
    setExaminerState("listening");
    setEvaluatingSince(null);

    const recordingId = ++recordingIdRef.current;
    const recorder = new AudioStreamRecorder({
      onAudioChunk: (chunkB64, chunkIndex) => {
        if (recordingId !== recordingIdRef.current) return; // recording was abandoned
        const question = questionRef.current;
        if (question) wsClientRef.current?.sendAudioChunk(question.turn_id, chunkIndex, chunkB64);
      },
      onVolumeChange: setAudioLevel,
      onSpeechEnd: (durationMs) => void submitAnswer(durationMs),
    });
    recorderRef.current = recorder;
    recorder.start().catch((err) => {
      recorderRef.current = null;
      setLiveError(errorMessage(err, "Microphone unavailable. Please allow microphone access and retry."));
    });

    const w = window as SpeechWindow;
    const Recognition = w.SpeechRecognition || w.webkitSpeechRecognition;
    const captionsUnavailable =
      "Live captions aren't available in this browser (use Chrome or Edge to see them). " +
      "Your answer is still being recorded and will be transcribed when you submit.";
    if (!Recognition) {
      setCaptionsNote(captionsUnavailable);
      return;
    }
    try {
      const recognition = new Recognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "en-IN";
      recognition.onresult = (event) => {
        let interim = "";
        let final = "";
        for (let i = 0; i < event.results.length; ++i) {
          const result = event.results[i];
          if (result.isFinal) final += result[0].transcript;
          else interim += result[0].transcript;
        }
        updateTranscript(final || interim);
      };
      // Brave and some Chromium builds expose the API but every request fails ("network",
      // "service-not-allowed"). Say so instead of leaving the box on "Awaiting speech input".
      recognition.onerror = (event) => {
        if (BENIGN_CAPTION_ERRORS.has(event.error)) return;
        recognition.onend = null;
        if (recognitionRef.current === recognition) recognitionRef.current = null;
        setCaptionsNote(captionsUnavailable);
      };
      // Chrome ends "continuous" recognition after a pause; restart it while this answer is live.
      recognition.onend = () => {
        if (recognitionRef.current !== recognition) return;
        try {
          recognition.start();
        } catch {
          recognitionRef.current = null;
        }
      };
      recognition.start();
      recognitionRef.current = recognition;
    } catch (err) {
      console.warn("Live captions unavailable", err);
    }
  };

  // Play the server's neural TTS when provided; fall back to browser speech synthesis.
  const speakQuestion = (question: QuestionPayload) => {
    // A question can arrive while the mic is open (repeat, or a reconnect replaying it).
    if (recorderRef.current) abandonListening();
    setEvaluatingSince(null);
    setExaminerState("examiner_speaking");
    listenedForQuestionRef.current = false;
    if (speechWatchdogRef.current) clearTimeout(speechWatchdogRef.current);
    if (utteranceRef.current) {
      utteranceRef.current.onend = null;
      utteranceRef.current.onerror = null;
    }
    playbackRef.current?.pause();
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();

    const browserSpeak = () => {
      if (!("speechSynthesis" in window)) {
        startListening();
        return;
      }
      const utterance = new SpeechSynthesisUtterance(question.question_text);
      utterance.rate = 0.95; // Calm, deliberate examiner pace
      utterance.onend = startListening;
      utterance.onerror = startListening;
      utteranceRef.current = utterance;
      window.speechSynthesis.speak(utterance);
      // Chrome sometimes never fires onend/onerror (long sentences, network voices, blocked autoplay).
      // Open the microphone anyway once the question should have finished (~2.5 words/s + margin).
      const words = question.question_text.split(/\s+/).length;
      speechWatchdogRef.current = setTimeout(startListening, (words / 2.5) * 1000 + 3000);
    };

    if (!question.audio_b64) {
      browserSpeak();
      return;
    }
    const audio = new Audio(`data:${question.audio_mime ?? "audio/mpeg"};base64,${question.audio_b64}`);
    playbackRef.current = audio;
    audio.onended = startListening;
    audio.onerror = browserSpeak;
    audio.play().catch(browserSpeak);
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
          questionRef.current = q;
          setCurrentQuestion(q);
          setCurrentTurnIndex(q.turn_number - 1);
          if (!q.is_repeat) setRepeatedCount(0);
          speakQuestion(q);
        },
        onTranscript: (text) => {
          if (text) updateTranscript(text);
        },
        onFeedback: (fb) => {
          const question = questionRef.current;
          const completedTurn: Turn = {
            id: fb.turn_id,
            turn_number: question?.turn_number ?? 0,
            question_text: question?.question_text ?? "",
            question_type: question?.question_type ?? "",
            topic: question?.topic ?? "",
            transcript: transcriptRef.current.trim(),
            score_0_10: fb.score_0_10 ?? undefined,
            rubric_breakdown: fb.rubric,
            feedback: fb.feedback,
            authenticity_likelihood: fb.authenticity.likelihood,
            authenticity_confidence: fb.authenticity.confidence ?? undefined,
            authenticity_reasons: fb.authenticity.reasons ?? [],
          };
          setTurns((prev) => [...prev, completedTurn]);
          setEvaluatingSince(null);
          ws.sendReady();
        },
        onSessionComplete: () => {
          setExaminerState("completed");
          ws.disconnect();
        },
        onStateChange: (st) => {
          // Speaking/listening are driven by local playback and the mic; the server
          // is authoritative for processing and completion.
          if (st === "processing" || st === "completed") setExaminerState(st);
          if (st === "processing") setEvaluatingSince((since) => since ?? Date.now());
        },
        onError: (err) => {
          setLiveError(err.message || "An error occurred during examination.");
          // The server kept the question open (nothing heard / transcription failed): reopen the
          // mic so the student can answer again instead of being stuck on "Evaluating".
          if (RETRY_ANSWER_CODES.has(err.code) && questionRef.current) {
            listenedForQuestionRef.current = false;
            startListening();
          }
        },
      }, { getTicket: () => api.getWsTicket(sess.id) });

      ws.connect();
      wsClientRef.current = ws;
    } catch (err) {
      setIsInitializing(false);
      setLiveError(errorMessage(err, "Failed to start viva session. Please check connection and retry."));
    }
  };

  const handleSubmitAnswer = () => void submitAnswer();

  // Repeat question (at most 1 repeat per turn); the server replays it as an is_repeat question.
  const handleRepeatQuestion = async () => {
    const question = questionRef.current;
    if (repeatedCount >= 1 || !question) return;
    setRepeatedCount((c) => c + 1);
    abandonListening(); // what was said so far is discarded; the student answers after the repeat
    wsClientRef.current?.sendRepeatQuestion(question.turn_id);
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8 text-[var(--text-primary)]">
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
                  {examinerState === "processing" &&
                    (evaluatingSince ? <EvaluationTimer since={evaluatingSince} /> : "Transcribing and grading your answer…")}
                </div>
              </div>

              {examinerState === "examiner_speaking" && currentQuestion && (
                <Button size="sm" variant="outline" onClick={startListening}>
                  <Mic className="w-3.5 h-3.5 mr-1.5" />
                  I&rsquo;m ready to answer
                </Button>
              )}
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
                  &ldquo;{currentQuestion?.question_text || "Preparing your next grounded question..."}&rdquo;
                </div>

                {examinerState === "completed" ? (
                  <p className="p-4 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)] text-sm text-[var(--text-secondary)]">
                    Your viva is complete. Your teacher will review the recording, transcript and scores.
                  </p>
                ) : (
                  <>
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
                        {currentTranscript
                          ? `“${currentTranscript}”`
                          : examinerState === "listening"
                            ? "(Speak now — your words will appear here…)"
                            : "(Awaiting speech input...)"}
                      </p>
                      {captionsNote && examinerState === "listening" && !currentTranscript && (
                        <p className="text-[11px] text-[var(--text-muted)] not-italic">{captionsNote}</p>
                      )}
                    </div>

                    {/* Control Actions */}
                    <div className="flex items-center justify-between pt-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={async () => {
                          await stopListening();
                          wsClientRef.current?.sendEndSession();
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
                  </>
                )}
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
                        {t.question_type === "warmup" ? "Warm-up · not scored" : `${t.score_0_10 ?? "—"}/10`}
                      </span>
                    </div>
                    <p className="text-xs text-[var(--text-secondary)] italic">&ldquo;{t.transcript}&rdquo;</p>
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

import { useEffect, useState } from "react";
import { Loader2, Play } from "lucide-react";
import { api } from "@/lib/api";

interface TurnAudioProps {
  sessionId: string;
  turnId: string;
}

/** Loads a turn's recording on demand (authenticated) and shows a native audio player. */
export default function TurnAudio({ sessionId, turnId }: TurnAudioProps) {
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [url]);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const blob = await api.getTurnAudio(sessionId, turnId);
      setUrl(URL.createObjectURL(blob));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Recording unavailable");
    } finally {
      setLoading(false);
    }
  };

  if (url) {
    return (
      // The transcript is shown alongside, which serves as the text alternative.
      <audio controls autoPlay src={url} className="w-full h-9" aria-label="Student's recorded answer" />
    );
  }

  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={() => void load()}
        disabled={loading}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-semibold rounded-lg border border-[var(--border-default)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card-hover)] transition-colors disabled:opacity-60 cursor-pointer"
      >
        {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
        Play recording
      </button>
      {error && <span className="text-[11px] text-[var(--text-muted)]">{error}</span>}
    </div>
  );
}

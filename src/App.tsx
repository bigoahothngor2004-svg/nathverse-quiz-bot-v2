import React, { useState, useEffect } from "react";
import {
  Send,
  Terminal,
  Clock,
  Award,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  FileCode,
  Copy,
  Check,
  Download,
  Plus,
  Trash2,
  Sparkles,
  Layers,
  Database,
  Shield,
  Bot,
  RefreshCw,
  ExternalLink,
  ChevronRight,
  Info
} from "lucide-react";

interface QuestionItem {
  text: string;
  options: string[];
  answer: string;
  explanation: string;
}

interface QuizBatch {
  batch_number: number;
  title: string;
  questions: QuestionItem[];
}

const DEFAULT_BATCH: QuizBatch = {
  batch_number: 1,
  title: "Math: Mixed Practical Word Problems I",
  questions: [
    {
      text: "If 6 shirts and 5 pants cost $120, and 5 shirts and 5 pants cost $90, how much does 1 shirt cost?",
      options: ["$15", "$30", "$25", "$20"],
      answer: "B",
      explanation: "Because 6 shirts - 5 shirts = 1 shirt, and $120 - $90 = $30."
    },
    {
      text: "A cyclist travels at 15 km/h for 2 hours, then rests for 30 minutes, and finishes 10 km in 30 minutes. What was the average cycling speed (excluding rest)?",
      options: ["16 km/h", "18 km/h", "20 km/h", "15 km/h"],
      answer: "A",
      explanation: "Total cycling distance = (15 * 2) + 10 = 40 km. Total cycling time = 2h + 0.5h = 2.5h. Average speed = 40 / 2.5 = 16 km/h."
    },
    {
      text: "In a class of 40 students, 25 play football, 20 play basketball, and 8 play neither. How many students play both sports?",
      options: ["10", "13", "15", "18"],
      answer: "B",
      explanation: "Students playing at least one sport = 40 - 8 = 32. Both = (25 + 20) - 32 = 13."
    }
  ]
};

export default function App() {
  const [activeTab, setActiveTab] = useState<"overview" | "generator" | "simulator" | "code">("overview");
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // Batch builder state
  const [batchData, setBatchData] = useState<QuizBatch>(DEFAULT_BATCH);
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [activeQuestionIdx, setActiveQuestionIdx] = useState(0);

  // Simulator state
  const [simPoints, setSimPoints] = useState(0);
  const [simAttemptCount, setSimAttemptCount] = useState(0);
  const [simCorrectCount, setSimCorrectCount] = useState(0);
  const [simCooldownRemaining, setSimCooldownRemaining] = useState<number>(0);
  const [simAlertModal, setSimAlertModal] = useState<{ title: string; body: string; isError?: boolean } | null>(null);
  const [simSelectedAnswers, setSimSelectedAnswers] = useState<Record<number, string>>({});

  // Cooldown countdown timer
  useEffect(() => {
    if (simCooldownRemaining <= 0) return;
    const interval = setInterval(() => {
      setSimCooldownRemaining((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(interval);
  }, [simCooldownRemaining]);

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const downloadJson = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(batchData, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `batch_${batchData.batch_number}_quiz.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const handleSimAnswer = (qIndex: number, optionLetter: string) => {
    // 1. Check if user already answered this question
    if (simSelectedAnswers[qIndex]) {
      setSimAlertModal({
        title: "⚠️ Already Answered",
        body: "You have already submitted an answer for this question!",
        isError: true
      });
      return;
    }

    // 2. Check cooldown
    if (simCooldownRemaining > 0) {
      const h = Math.floor(simCooldownRemaining / 3600);
      const m = Math.floor((simCooldownRemaining % 3600) / 60);
      const s = simCooldownRemaining % 60;
      const formatted = `${h > 0 ? h + "h " : ""}${m}m ${s}s`;
      setSimAlertModal({
        title: "⏳ Cooldown Active!",
        body: `Please wait ${formatted} before your next attempt.\n\nProgressive cooldown resets 24h after attempts.`,
        isError: true
      });
      return;
    }

    const currentQ = batchData.questions[qIndex];
    const isCorrect = optionLetter.toUpperCase() === currentQ.answer.toUpperCase();

    // Mark as answered
    setSimSelectedAnswers((prev) => ({ ...prev, [qIndex]: optionLetter }));

    // Update attempts and score
    const newAttemptCount = simAttemptCount + 1;
    setSimAttemptCount(newAttemptCount);

    if (isCorrect) {
      setSimPoints((prev) => prev + 3);
      setSimCorrectCount((prev) => prev + 1);
      setSimAlertModal({
        title: "Telegram Alert",
        body: "✅ Correct! +3 points added."
      });
    } else {
      setSimPoints((prev) => Math.max(0, prev - 1));
      setSimAlertModal({
        title: "Telegram Alert",
        body: `❌ Incorrect! (Correct answer was ${currentQ.answer})\n\n💡 Explanation:\n${currentQ.explanation}\n\n-1 point applied.`
      });
    }

    // Determine next cooldown based on number of attempts
    // 1st attempt: 1h cooldown (3600s)
    // 2nd attempt: 6h cooldown (21600s)
    // 3rd+ attempt: 24h cooldown (86400s)
    if (newAttemptCount === 1) {
      setSimCooldownRemaining(3600);
    } else if (newAttemptCount === 2) {
      setSimCooldownRemaining(21600);
    } else {
      setSimCooldownRemaining(86400);
    }
  };

  const resetSimulator = () => {
    setSimPoints(0);
    setSimAttemptCount(0);
    setSimCorrectCount(0);
    setSimCooldownRemaining(0);
    setSimSelectedAnswers({});
    setSimAlertModal(null);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-cyan-500/30 selection:text-cyan-200">
      {/* Top Header */}
      <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-600 via-indigo-600 to-violet-600 p-[1px] shadow-lg shadow-cyan-500/10">
              <div className="w-full h-full bg-slate-900 rounded-[11px] flex items-center justify-center">
                <Bot className="w-5 h-5 text-cyan-400" />
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
                  NathVerse
                </span>
                <span className="px-2 py-0.5 text-[11px] font-semibold bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 rounded-full">
                  Telegram Quiz Bot
                </span>
              </div>
              <p className="text-xs text-slate-400">Python 3.11 • Async PTB v20 • APScheduler • SQLite3</p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex items-center gap-1 sm:gap-2">
            <button
              id="tab-overview"
              onClick={() => setActiveTab("overview")}
              className={`px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-all ${
                activeTab === "overview"
                  ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
              }`}
            >
              Overview & Rules
            </button>
            <button
              id="tab-generator"
              onClick={() => setActiveTab("generator")}
              className={`px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-all ${
                activeTab === "generator"
                  ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
              }`}
            >
              Batch Builder
            </button>
            <button
              id="tab-simulator"
              onClick={() => setActiveTab("simulator")}
              className={`px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-all ${
                activeTab === "simulator"
                  ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
              }`}
            >
              Live Simulator
            </button>
            <button
              id="tab-code"
              onClick={() => setActiveTab("code")}
              className={`px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-all ${
                activeTab === "code"
                  ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
              }`}
            >
              Source Files
            </button>
          </nav>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* OVERVIEW TAB */}
        {activeTab === "overview" && (
          <div className="space-y-8 animate-fadeIn">
            {/* Hero Banner */}
            <div className="relative overflow-hidden rounded-2xl border border-slate-800 bg-gradient-to-b from-slate-900 via-slate-900/90 to-slate-950 p-6 sm:p-8">
              <div className="absolute -right-16 -top-16 w-64 h-64 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
              <div className="absolute right-32 bottom-0 w-48 h-48 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

              <div className="max-w-3xl space-y-4">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium bg-cyan-950/80 text-cyan-300 border border-cyan-800/50">
                  <Sparkles className="w-3.5 h-3.5" />
                  Production Ready Architecture
                </div>
                <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-white">
                  Automated Quiz Broadcasts, Progressive Cooldowns & Instant Modal Alerts
                </h1>
                <p className="text-slate-300 text-sm sm:text-base leading-relaxed">
                  NathVerse runs as an autonomous Telegram bot designed for educational channels and trivia communities.
                  It delivers batch questions every 720 minutes, calculates progressive 24-hour cooldown windows,
                  and provides instant alert popups via Telegram callback queries.
                </p>
              </div>

              {/* Status metrics */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8 pt-6 border-t border-slate-800/80">
                <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/60">
                  <div className="flex items-center gap-2 text-slate-400 text-xs font-medium">
                    <Clock className="w-3.5 h-3.5 text-cyan-400" /> Broadcast Interval
                  </div>
                  <div className="text-lg font-bold text-white mt-1">720 Mins</div>
                  <div className="text-[11px] text-slate-400">Every 12 Hours</div>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/60">
                  <div className="flex items-center gap-2 text-slate-400 text-xs font-medium">
                    <Award className="w-3.5 h-3.5 text-amber-400" /> Scoring Engine
                  </div>
                  <div className="text-lg font-bold text-white mt-1">+3 / -1</div>
                  <div className="text-[11px] text-slate-400">Floor at 0 points</div>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/60">
                  <div className="flex items-center gap-2 text-slate-400 text-xs font-medium">
                    <Shield className="w-3.5 h-3.5 text-emerald-400" /> Cooldown Ladder
                  </div>
                  <div className="text-lg font-bold text-white mt-1">0h → 1h → 6h → 24h</div>
                  <div className="text-[11px] text-slate-400">Past 24-hour attempts</div>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/60">
                  <div className="flex items-center gap-2 text-slate-400 text-xs font-medium">
                    <Database className="w-3.5 h-3.5 text-indigo-400" /> SQLite Persistence
                  </div>
                  <div className="text-lg font-bold text-white mt-1">WAL Mode</div>
                  <div className="text-[11px] text-slate-400">Safe concurrent locks</div>
                </div>
              </div>
            </div>

            {/* Core Specifications Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Cooldown Policy Card */}
              <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
                    <Clock className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-white">Progressive Cooldown Policy</h3>
                    <p className="text-xs text-slate-400">Enforces deliberate thought & anti-spamming</p>
                  </div>
                </div>

                <p className="text-xs text-slate-300 leading-relaxed">
                  Every user attempt is timestamped in UTC. When an answer button is tapped, the bot counts past attempts
                  within the last 24-hour rolling window:
                </p>

                <div className="space-y-2 text-xs">
                  <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 flex items-center justify-between">
                    <span className="font-semibold text-slate-200">1st Attempt (0 prior in 24h)</span>
                    <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                      Immediate (0s)
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 flex items-center justify-between">
                    <span className="font-semibold text-slate-200">2nd Attempt (1 prior in 24h)</span>
                    <span className="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-mono">
                      1-Hour Wait (3,600s)
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 flex items-center justify-between">
                    <span className="font-semibold text-slate-200">3rd Attempt (2 prior in 24h)</span>
                    <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 font-mono">
                      6-Hour Wait (21,600s)
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 flex items-center justify-between">
                    <span className="font-semibold text-slate-200">4th+ Attempt (3+ prior in 24h)</span>
                    <span className="px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20 font-mono">
                      24-Hour Wait (86,400s)
                    </span>
                  </div>
                </div>
              </div>

              {/* Bot Commands & Handlers */}
              <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
                    <Terminal className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-white">Bot Command Reference</h3>
                    <p className="text-xs text-slate-400">Telegram event handlers and permissions</p>
                  </div>
                </div>

                <div className="space-y-2 text-xs">
                  <div className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800/80 flex items-start gap-2">
                    <code className="text-cyan-400 font-mono font-semibold">/start</code>
                    <span className="text-slate-300">Overview of NathVerse, scoring system, cooldown policy, and command manual.</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800/80 flex items-start gap-2">
                    <code className="text-cyan-400 font-mono font-semibold">/leaderboard</code>
                    <span className="text-slate-300">Top 5 players display with Points, Questions Attempted, and Accuracy %.</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800/80 flex items-start gap-2">
                    <code className="text-cyan-400 font-mono font-semibold">/stats (or /me)</code>
                    <span className="text-slate-300">User's individual score, rank, attempted questions, accuracy, and cooldown timer.</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800/80 flex items-start gap-2">
                    <code className="text-amber-400 font-mono font-semibold">/addquiz</code>
                    <span className="text-slate-300">Admin-only: upload `.json` document schema with validation and error reporting.</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800/80 flex items-start gap-2">
                    <code className="text-amber-400 font-mono font-semibold">/postbatch</code>
                    <span className="text-slate-300">Admin-only: manually triggers immediate broadcast of next unposted batch.</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* BATCH BUILDER TAB */}
        {activeTab === "generator" && (
          <div className="space-y-6 animate-fadeIn">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <Layers className="w-5 h-5 text-cyan-400" />
                  Quiz Batch Builder & Validator
                </h2>
                <p className="text-xs text-slate-400">
                  Compose batch questions, validate formatting, and export ready-to-upload `.json` documents for <code>/addquiz</code>.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  id="btn-copy-json"
                  onClick={() => copyToClipboard(JSON.stringify(batchData, null, 2), "batch-json")}
                  className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-slate-700 flex items-center gap-2 transition"
                >
                  {copiedKey === "batch-json" ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                  {copiedKey === "batch-json" ? "Copied!" : "Copy JSON"}
                </button>
                <button
                  id="btn-download-json"
                  onClick={downloadJson}
                  className="px-3 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-xs font-semibold text-white shadow-lg shadow-cyan-600/20 flex items-center gap-2 transition"
                >
                  <Download className="w-4 h-4" />
                  Download .json
                </button>
              </div>
            </div>

            {/* Editor & Preview Split */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Question Editor */}
              <div className="lg:col-span-7 space-y-4">
                <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/60 space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-slate-400 mb-1">Batch Number</label>
                      <input
                        type="number"
                        min="1"
                        value={batchData.batch_number}
                        onChange={(e) => setBatchData({ ...batchData, batch_number: parseInt(e.target.value) || 1 })}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500"
                      />
                    </div>
                    <div className="sm:col-span-2">
                      <label className="block text-xs font-semibold text-slate-400 mb-1">Batch Title</label>
                      <input
                        type="text"
                        value={batchData.title}
                        onChange={(e) => setBatchData({ ...batchData, title: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500"
                      />
                    </div>
                  </div>

                  {/* Question Tabs */}
                  <div className="pt-2 border-t border-slate-800/80">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs font-semibold text-slate-400">Questions ({batchData.questions.length})</span>
                      <button
                        onClick={() => {
                          const newQ: QuestionItem = {
                            text: "New sample question text?",
                            options: ["Option A", "Option B", "Option C", "Option D"],
                            answer: "A",
                            explanation: "Step-by-step reasoning for the correct answer."
                          };
                          setBatchData({ ...batchData, questions: [...batchData.questions, newQ] });
                          setActiveQuestionIdx(batchData.questions.length);
                        }}
                        className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-cyan-300 flex items-center gap-1 border border-slate-700"
                      >
                        <Plus className="w-3.5 h-3.5" /> Add Question
                      </button>
                    </div>

                    <div className="flex gap-2 overflow-x-auto pb-2">
                      {batchData.questions.map((_, i) => (
                        <button
                          key={i}
                          onClick={() => setActiveQuestionIdx(i)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition ${
                            activeQuestionIdx === i
                              ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                              : "bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800"
                          }`}
                        >
                          Q{i + 1}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Active Question Fields */}
                  {batchData.questions[activeQuestionIdx] && (
                    <div className="space-y-4 pt-2">
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <label className="text-xs font-semibold text-slate-400">Question Text</label>
                          {batchData.questions.length > 1 && (
                            <button
                              onClick={() => {
                                const updated = batchData.questions.filter((_, i) => i !== activeQuestionIdx);
                                setBatchData({ ...batchData, questions: updated });
                                setActiveQuestionIdx(Math.max(0, activeQuestionIdx - 1));
                              }}
                              className="text-xs text-rose-400 hover:text-rose-300 flex items-center gap-1"
                            >
                              <Trash2 className="w-3.5 h-3.5" /> Delete
                            </button>
                          )}
                        </div>
                        <textarea
                          rows={2}
                          value={batchData.questions[activeQuestionIdx].text}
                          onChange={(e) => {
                            const updated = [...batchData.questions];
                            updated[activeQuestionIdx].text = e.target.value;
                            setBatchData({ ...batchData, questions: updated });
                          }}
                          className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-sm text-white focus:outline-none focus:border-cyan-500"
                        />
                      </div>

                      {/* Options */}
                      <div>
                        <label className="block text-xs font-semibold text-slate-400 mb-2">Options (4 choices)</label>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {batchData.questions[activeQuestionIdx].options.map((opt, optIdx) => {
                            const letter = ["A", "B", "C", "D"][optIdx];
                            const isSelectedAnswer = batchData.questions[activeQuestionIdx].answer === letter;
                            return (
                              <div key={optIdx} className="flex items-center gap-2 bg-slate-950 p-2 rounded-xl border border-slate-800">
                                <button
                                  type="button"
                                  onClick={() => {
                                    const updated = [...batchData.questions];
                                    updated[activeQuestionIdx].answer = letter;
                                    setBatchData({ ...batchData, questions: updated });
                                  }}
                                  title="Mark as correct answer"
                                  className={`w-7 h-7 rounded-lg text-xs font-bold transition flex items-center justify-center ${
                                    isSelectedAnswer
                                      ? "bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/30"
                                      : "bg-slate-800 text-slate-400 hover:bg-slate-700"
                                  }`}
                                >
                                  {letter}
                                </button>
                                <input
                                  type="text"
                                  value={opt}
                                  onChange={(e) => {
                                    const updated = [...batchData.questions];
                                    updated[activeQuestionIdx].options[optIdx] = e.target.value;
                                    setBatchData({ ...batchData, questions: updated });
                                  }}
                                  className="flex-1 bg-transparent text-xs text-white focus:outline-none"
                                />
                              </div>
                            );
                          })}
                        </div>
                      </div>

                      {/* Explanation */}
                      <div>
                        <label className="block text-xs font-semibold text-slate-400 mb-1">
                          Explanation (Displayed in modal alert on wrong answer)
                        </label>
                        <textarea
                          rows={2}
                          value={batchData.questions[activeQuestionIdx].explanation}
                          onChange={(e) => {
                            const updated = [...batchData.questions];
                            updated[activeQuestionIdx].explanation = e.target.value;
                            setBatchData({ ...batchData, questions: updated });
                          }}
                          className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-sm text-white focus:outline-none focus:border-cyan-500"
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* JSON Live Output Preview */}
              <div className="lg:col-span-5 space-y-4">
                <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/60 flex flex-col h-full">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                      <FileCode className="w-4 h-4 text-cyan-400" />
                      JSON Schema Output
                    </span>
                    <span className="text-[11px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                      Validated Schema
                    </span>
                  </div>

                  <pre className="flex-1 overflow-auto p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-cyan-300 leading-relaxed max-h-[440px]">
                    {JSON.stringify(batchData, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* LIVE SIMULATOR TAB */}
        {activeTab === "simulator" && (
          <div className="space-y-6 animate-fadeIn">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <Bot className="w-5 h-5 text-cyan-400" />
                  Interactive Bot & Channel Simulator
                </h2>
                <p className="text-xs text-slate-400">
                  Experience how NathVerse behaves inside Telegram: tap option buttons, test cooldown timeouts, and inspect alert popups.
                </p>
              </div>

              <button
                onClick={resetSimulator}
                className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 border border-slate-700 flex items-center gap-1.5 transition self-start sm:self-auto"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Reset Simulator
              </button>
            </div>

            {/* Stats bar */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800">
                <span className="text-xs text-slate-400 font-medium">Your Points</span>
                <div className="text-2xl font-bold text-amber-400 mt-1">{simPoints}</div>
                <span className="text-[11px] text-slate-400">+3 correct, -1 wrong (floor: 0)</span>
              </div>

              <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800">
                <span className="text-xs text-slate-400 font-medium">Questions Attempted</span>
                <div className="text-2xl font-bold text-white mt-1">{simAttemptCount}</div>
                <span className="text-[11px] text-slate-400">{simCorrectCount} Correct</span>
              </div>

              <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800">
                <span className="text-xs text-slate-400 font-medium">Accuracy</span>
                <div className="text-2xl font-bold text-emerald-400 mt-1">
                  {simAttemptCount > 0 ? ((simCorrectCount / simAttemptCount) * 100).toFixed(1) : "0.0"}%
                </div>
                <span className="text-[11px] text-slate-400">Leaderboard Metric</span>
              </div>

              <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800">
                <span className="text-xs text-slate-400 font-medium">Cooldown State</span>
                <div className={`text-xl font-bold mt-1 ${simCooldownRemaining > 0 ? "text-rose-400" : "text-emerald-400"}`}>
                  {simCooldownRemaining > 0
                    ? `${Math.floor(simCooldownRemaining / 60)}m ${simCooldownRemaining % 60}s`
                    : "Ready"}
                </div>
                <span className="text-[11px] text-slate-400">
                  {simAttemptCount === 0 ? "1st attempt immediate" : simAttemptCount === 1 ? "1h cooldown active" : simAttemptCount === 2 ? "6h cooldown active" : "24h cooldown active"}
                </span>
              </div>
            </div>

            {/* Telegram Channel Simulator Screen */}
            <div className="max-w-2xl mx-auto rounded-3xl border border-slate-800 bg-[#0f172a] shadow-2xl overflow-hidden">
              {/* Channel Header */}
              <div className="bg-slate-900 px-5 py-3 border-b border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-cyan-600 to-indigo-600 flex items-center justify-center font-bold text-white text-sm shadow">
                    NV
                  </div>
                  <div>
                    <div className="font-bold text-sm text-white flex items-center gap-1.5">
                      NathVerse Official Channel
                      <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400 fill-cyan-400/20" />
                    </div>
                    <div className="text-[11px] text-slate-400">@nathverse_channel • 12.4k subscribers</div>
                  </div>
                </div>

                <div className="px-2.5 py-1 rounded-full bg-slate-800 text-[11px] font-medium text-slate-300">
                  Broadcast View
                </div>
              </div>

              {/* Messages Feed */}
              <div className="p-5 space-y-6 max-h-[600px] overflow-y-auto">
                {/* Batch Announcement Banner Message */}
                <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-4 space-y-2 text-xs">
                  <div className="font-bold text-cyan-400 flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4" />
                    NATHVERSE QUIZ CHALLENGE
                  </div>
                  <div className="text-white font-medium">
                    📦 Batch #{batchData.batch_number}: {batchData.title}
                  </div>
                  <div className="text-slate-400">
                    📝 Questions in batch: {batchData.questions.length} • ⚡ Scoring: +3 for Correct | -1 for Incorrect
                  </div>
                  <div className="pt-2 text-slate-300 border-t border-slate-800">
                    👇 Tap your answers below to climb the leaderboard!
                  </div>
                </div>

                {/* Individual Question Messages */}
                {batchData.questions.map((q, qIndex) => {
                  const hasAnswered = !!simSelectedAnswers[qIndex];
                  const chosenLetter = simSelectedAnswers[qIndex];

                  return (
                    <div key={qIndex} className="rounded-2xl bg-slate-900/90 border border-slate-800 p-4 space-y-3">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-bold text-slate-300">
                          🧩 Question {qIndex + 1}/{batchData.questions.length}
                        </span>
                        {hasAnswered && (
                          <span className="text-[11px] px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-medium">
                            Answered: {chosenLetter}
                          </span>
                        )}
                      </div>

                      <p className="text-sm text-white leading-snug">{q.text}</p>

                      {/* Inline Keyboard Buttons */}
                      <div className="grid grid-cols-2 gap-2 pt-2">
                        {q.options.map((opt, optIndex) => {
                          const letter = ["A", "B", "C", "D"][optIndex];
                          const isPicked = chosenLetter === letter;

                          return (
                            <button
                              key={optIndex}
                              onClick={() => handleSimAnswer(qIndex, letter)}
                              className={`p-2.5 rounded-xl text-xs font-medium border text-left transition flex items-center justify-between ${
                                isPicked
                                  ? "bg-cyan-600/20 border-cyan-500 text-cyan-300"
                                  : "bg-slate-950/80 hover:bg-slate-800/80 border-slate-800 text-slate-200"
                              }`}
                            >
                              <span>
                                <strong className="text-cyan-400 mr-1.5">{letter}.</strong> {opt}
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Telegram Modal Alert Simulation */}
            {simAlertModal && (
              <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                <div className="max-w-sm w-full bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 space-y-4 animate-scaleUp">
                  <div className="flex items-center gap-3">
                    {simAlertModal.isError ? (
                      <div className="w-10 h-10 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400">
                        <AlertTriangle className="w-5 h-5" />
                      </div>
                    ) : (
                      <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
                        <CheckCircle2 className="w-5 h-5" />
                      </div>
                    )}
                    <div>
                      <h4 className="text-base font-bold text-white">{simAlertModal.title}</h4>
                      <p className="text-[11px] text-slate-400">Telegram Client show_alert Modal</p>
                    </div>
                  </div>

                  <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 whitespace-pre-line leading-relaxed font-sans">
                    {simAlertModal.body}
                  </div>

                  <button
                    onClick={() => setSimAlertModal(null)}
                    className="w-full py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 font-semibold text-xs text-white shadow-lg transition"
                  >
                    Dismiss Alert
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* SOURCE CODE TAB */}
        {activeTab === "code" && (
          <div className="space-y-6 animate-fadeIn">
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <FileCode className="w-5 h-5 text-cyan-400" />
                NathVerse Production Source Code
              </h2>
              <p className="text-xs text-slate-400">
                Inspect and copy all project files. Tested and ready for containerized deployment.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* bot.py Card */}
              <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/60 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm font-bold text-cyan-300">bot.py</span>
                  <span className="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-400">Telegram & APScheduler</span>
                </div>
                <p className="text-xs text-slate-400">
                  Event handlers, callback query router, APScheduler 720m trigger, JSON validator, and admin commands.
                </p>
                <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-400 space-y-1">
                  <div>• Async PTB v20+ <code>Application</code></div>
                  <div>• <code>show_alert=True</code> popup alerts</div>
                  <div>• <code>/addquiz</code>, <code>/postbatch</code>, <code>/leaderboard</code></div>
                </div>
              </div>

              {/* database.py Card */}
              <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/60 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm font-bold text-cyan-300">database.py</span>
                  <span className="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-400">SQLite & Lock Safety</span>
                </div>
                <p className="text-xs text-slate-400">
                  SQLite database schema, WAL mode, progressive 24h cooldown calculator, score floor at 0, and leaderboard queries.
                </p>
                <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-400 space-y-1">
                  <div>• <code>users</code>, <code>attempts</code>, <code>quizzes</code> tables</div>
                  <div>• Immediate → 1h → 6h → 24h ladder</div>
                  <div>• Thread & concurrency lock safety</div>
                </div>
              </div>

              {/* Deployment Card */}
              <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/60 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm font-bold text-cyan-300">Dockerfile & Env</span>
                  <span className="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-400">Container Build</span>
                </div>
                <p className="text-xs text-slate-400">
                  Lightweight <code>python:3.11-slim</code> container with persistent volume mount at <code>/app/data</code>.
                </p>
                <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-400 space-y-1">
                  <div>• Volume: <code>/app/data</code></div>
                  <div>• <code>.env.example</code> with tokens & admin IDs</div>
                  <div>• <code>requirements.txt</code> dependencies</div>
                </div>
              </div>
            </div>

            {/* Quick Deployment Steps */}
            <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/60 space-y-4">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Terminal className="w-4 h-4 text-cyan-400" />
                Quick Launch Instructions
              </h3>
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-slate-300 space-y-2">
                <div><span className="text-slate-500"># 1. Configure environment variables</span></div>
                <div>cp .env.example .env</div>
                <div><span className="text-slate-500"># Edit .env and enter your BOT_TOKEN, CHANNEL_ID, and ADMIN_IDS</span></div>
                <div className="pt-2"><span className="text-slate-500"># 2. Build and launch Docker container</span></div>
                <div>docker build -t nathverse-bot .</div>
                <div>docker run -d --name nathverse -v $(pwd)/data:/app/data --env-file .env nathverse-bot</div>
                <div className="pt-2"><span className="text-slate-500"># 3. Verify execution via test suite</span></div>
                <div>python3 test_suite.py</div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Bottom Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-900/40 py-6 text-center text-xs text-slate-400">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>NathVerse Telegram Quiz Bot • Python 3.11 Slim</span>
          <span className="text-slate-400">APScheduler (720m) • Progressive Cooldown • SQLite3 WAL</span>
        </div>
      </footer>
    </div>
  );
}

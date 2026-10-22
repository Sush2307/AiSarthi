import { useEffect, useRef, useState, useCallback } from "react";
import { useLocation } from "react-router-dom";
import {
  AlertCircle,
  BarChart2,
  Bot,
  Database,
  Loader2,
  MessageSquare,
  Plus,
  RotateCw,
  Send,
  Table as TableIcon,
  Trash2,
  User,
  Sparkles,
} from "lucide-react";
import { api } from "../api";
import { useApi } from "../context";
import { demoQuery } from "../demo";
import type { EvidenceSummary, HealthRecord, HealthStatus } from "../types";
import { CompareBar, RecordsTable } from "../components/common";
import { FormattedMessage } from "../components/FormattedMessage";
import { SAMPLES } from "../constants";

interface Msg {
  id: number;
  role: "user" | "bot";
  text: string;
  records?: HealthRecord[];
  label?: string;
  evidence_summary?: EvidenceSummary | null;
  follow_ups?: string[];
  inference_mode?: string;
  fallback_used?: boolean;
  fallback_reason?: string | null;
  answer_type?: string;
  error?: string;
  retry?: string;
}

interface Conv {
  id: number;
  title: string;
  msgs: Msg[];
}

const STORAGE_KEY = "sarthi-chats";

const loadConvs = (): Conv[] => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((c): c is Conv => Boolean(c && typeof c.id === "number" && Array.isArray(c.msgs)))
      .map((c) => ({
        ...c,
        title: typeof c.title === "string" && c.title.trim() ? c.title : "Conversation",
        msgs: Array.isArray(c.msgs) ? c.msgs : [],
      }));
  } catch {
    return [];
  }
};

let uid = Date.now();

export default function Chat() {
  const { live } = useApi();
  const loc = useLocation();
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);

  useEffect(() => {
    if (live) {
      api.health().then(setHealthStatus).catch(() => {});
    }
  }, [live]);

  const [convs, setConvs] = useState<Conv[]>(() => {
    const loaded = loadConvs();
    return loaded.length ? loaded : [{ id: ++uid, title: "New Conversation", msgs: [] }];
  });

  const [active, setActive] = useState<number>(() => {
    const loaded = loadConvs();
    return loaded.length ? loaded[0].id : uid;
  });

  const [input, setInput] = useState(() => {
    return (loc.state as { prompt?: string } | null)?.prompt ?? "";
  });

  const [busy, setBusy] = useState(false);
  const [viewModes, setViewModes] = useState<Record<number, "table" | "chart">>({});
  const endRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const userScrolledUp = useRef<boolean>(false);

  // Sync prompt if passed via navigation
  useEffect(() => {
    const passedPrompt = (loc.state as { prompt?: string } | null)?.prompt;
    if (passedPrompt) {
      setInput(passedPrompt);
    }
  }, [loc.state]);

  // Persist conversation history to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(convs.slice(0, 20)));
    } catch {
      /* ignore storage quota errors */
    }
  }, [convs]);

  // Active conversation fallback
  const conv = convs.find((c) => c.id === active) ?? convs[0] ?? {
    id: uid,
    title: "New Conversation",
    msgs: [],
  };

  const msgs = conv.msgs ?? [];

  // Track if user scrolled up manually
  const handleScroll = useCallback(() => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 120;
    userScrolledUp.current = !isAtBottom;
  }, []);

  // Scroll to bottom only if user hasn't scrolled up
  useEffect(() => {
    if (!userScrolledUp.current) {
      endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [msgs.length, busy]);

  const patch = (fn: (m: Msg[]) => Msg[], titlePrompt?: string) => {
    setConvs((cs) =>
      cs.map((c) => {
        if (c.id !== conv.id) return c;
        const updatedMsgs = fn(c.msgs ?? []);
        let updatedTitle = c.title;
        if (
          (c.title === "New Conversation" || c.title === "New chat") &&
          titlePrompt &&
          titlePrompt.trim()
        ) {
          updatedTitle = titlePrompt.trim().slice(0, 36) + (titlePrompt.length > 36 ? "…" : "");
        }
        return {
          ...c,
          title: updatedTitle,
          msgs: updatedMsgs,
        };
      })
    );
  };

  async function send(text: string, isRetry = false) {
    const q = text.trim();
    if (q.length < 3 || busy) return;

    setInput("");
    setBusy(true);
    userScrolledUp.current = false;

    patch(
      (m) =>
        isRetry
          ? m.filter((x) => !x.error)
          : [...m, { id: ++uid, role: "user", text: q }],
      q
    );

    try {
      let bot: Msg;
      if (live) {
        const r = await api.chat(q);
        const hasRecords = Boolean(r.records && r.records.length > 0);
        let label = "Verified Dataset Records Only";

        if (r.inference_mode === "model-generated" || (r.answer_type === "ai_generated" && !r.fallback_used)) {
          label = "AI-Grounded Synthesis (Qwen3-1.7B • Verified Evidence)";
        } else if (r.fallback_used) {
          label = "Deterministic Retrieval Fallback (Model fallback)";
        } else if (r.mode === "verified-scheme" || r.inference_mode === "verified-scheme") {
          label = "Verified Government Healthcare Scheme";
        } else if (r.answer_type === "no_data" || !hasRecords) {
          label = "No Direct Records Found";
        }

        bot = {
          id: ++uid,
          role: "bot",
          text: r.answer,
          records: r.records ?? [],
          label,
          evidence_summary: r.evidence_summary,
          follow_ups: r.follow_ups,
          inference_mode: r.inference_mode,
          fallback_used: r.fallback_used,
          fallback_reason: r.fallback_reason,
          answer_type: r.answer_type,
        };
      } else {
        const rs = demoQuery({ q });
        bot = {
          id: ++uid,
          role: "bot",
          records: rs,
          label: "DEMO MODE – Sample data; no AI model connected",
          text: rs.length
            ? "Matching sample records found (demonstration only, not real healthcare statistics):"
            : "No matching sample records found in demo mode. Start the backend with the master dataset to query 1.18M+ real records.",
          follow_ups: [
            "Institutional births in Pune",
            "Anaemia in children across states",
          ],
        };
      }
      patch((m) => [...m, bot]);
    } catch (e) {
      patch((m) => [
        ...m,
        {
          id: ++uid,
          role: "bot",
          text: "",
          error: `Could not retrieve answer (${(e as Error).message}). Ensure the backend server is reachable.`,
          retry: q,
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  const newChat = () => {
    const newId = ++uid;
    const newC: Conv = { id: newId, title: "New Conversation", msgs: [] };
    setConvs([newC, ...convs]);
    setActive(newId);
  };

  const deleteChat = (idToDelete: number, e: React.MouseEvent) => {
    e.stopPropagation();
    const filtered = convs.filter((c) => c.id !== idToDelete);
    if (!filtered.length) {
      const fresh: Conv = { id: ++uid, title: "New Conversation", msgs: [] };
      setConvs([fresh]);
      setActive(fresh.id);
    } else {
      setConvs(filtered);
      if (active === idToDelete) {
        setActive(filtered[0].id);
      }
    }
  };

  return (
    <div className="grid gap-6 md:grid-cols-[280px_1fr] lg:grid-cols-[320px_1fr] items-start w-full">
      {/* Sidebar: Conversation History */}
      <aside
        className="card flex flex-col gap-3 p-4 md:sticky md:top-20 max-h-[82vh] overflow-hidden bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700"
        aria-label="Conversation history"
      >
        <button className="btn w-full justify-center" onClick={newChat}>
          <Plus size={15} />
          New Conversation
        </button>

        <div className="border-t border-ivory-200 dark:border-night-750 pt-2">
          <div className="text-[11px] font-bold uppercase tracking-wider text-pine-500 dark:text-pine-400 px-2 mb-1.5">
            Saved Conversations ({convs.length})
          </div>
          <ul className="space-y-1 overflow-y-auto max-h-56 md:max-h-[58vh] pr-1">
            {convs.map((c) => {
              const isSelected = c.id === conv.id;
              return (
                <li key={c.id}>
                  <button
                    onClick={() => {
                      setActive(c.id);
                      userScrolledUp.current = false;
                    }}
                    className={`group flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-xs transition-colors ${
                      isSelected
                        ? "bg-brand-50 font-semibold text-brand-900 dark:bg-night-800 dark:text-brand-300 border border-brand-200 dark:border-night-700"
                        : "text-pine-600 hover:bg-ivory-100 dark:text-pine-300 dark:hover:bg-night-800"
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate pr-1">
                      <MessageSquare size={13} className={isSelected ? "text-brand-700 dark:text-brand-400" : "text-pine-400"} />
                      <span className="truncate">{c.title || "Conversation"}</span>
                    </div>
                    {convs.length > 1 && (
                      <span
                        onClick={(e) => deleteChat(c.id, e)}
                        className="opacity-0 group-hover:opacity-100 text-pine-400 hover:text-alert-error transition-opacity p-0.5 rounded"
                        title="Delete conversation"
                      >
                        <Trash2 size={12} />
                      </span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      </aside>

      {/* Main Chat Conversation View */}
      <section className="card flex flex-col p-4 sm:p-6 min-h-[78vh] max-h-[82vh] relative overflow-hidden bg-white dark:bg-night-850 border-ivory-300 dark:border-night-700">
        {/* Chat Header */}
        <div className="flex items-center justify-between border-b border-ivory-200 pb-3 mb-2 dark:border-night-750 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="rounded-lg bg-brand-50 p-2 text-brand-800 dark:bg-brand-950 dark:text-brand-300">
              <Bot size={17} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-pine-900 dark:text-white truncate max-w-[280px] sm:max-w-md">
                {conv.title || "Healthcare Assistant"}
              </h2>
              <div className="flex flex-wrap items-center gap-2 mt-0.5">
                <p className="text-[11px] muted">
                  {live
                    ? "Evidence-grounded against 1.18M+ government health records"
                    : "Demo Mode (Mock dataset)"}
                </p>
                {live && healthStatus && (
                  <span
                    className={`inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
                      healthStatus.model_available
                        ? "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800"
                        : "bg-blue-50 text-blue-800 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800"
                    }`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${healthStatus.model_available ? "bg-emerald-500" : "bg-blue-500"}`} />
                    {healthStatus.model_available
                      ? `Qwen3-1.7B (${healthStatus.device})`
                      : "Evidence-Grounded Retrieval Active"}
                  </span>
                )}
              </div>
            </div>
          </div>
          <button
            onClick={() => patch(() => [])}
            className="btn-o text-xs py-1 px-2.5 rounded-lg"
            title="Clear messages in this conversation"
            disabled={!msgs.length}
          >
            Clear Thread
          </button>
        </div>

        {/* Message Thread */}
        <div
          ref={containerRef}
          onScroll={handleScroll}
          className="flex-1 space-y-4 overflow-y-auto pr-1.5 py-2"
          aria-live="polite"
        >
          {/* Welcome Screen when Empty */}
          {!msgs.length && (
            <div className="py-10 text-center space-y-5 max-w-xl mx-auto">
              <div className="mx-auto w-12 h-12 rounded-xl bg-brand-50 dark:bg-brand-950 flex items-center justify-center text-brand-800 dark:text-brand-300">
                <Sparkles size={22} />
              </div>
              <div className="space-y-1.5">
                <h3 className="text-base font-bold text-pine-900 dark:text-white">
                  Ask AI Sarthi about Indian Healthcare Data
                </h3>
                <p className="muted text-xs leading-relaxed max-w-md mx-auto">
                  Inquiries are resolved by retrieving matching indicators from HMIS, NFHS-5, and AHS public datasets. Select an example to begin:
                </p>
              </div>

              <div className="grid gap-2 text-left pt-2">
                {SAMPLES.map((s) => (
                  <button
                    key={s}
                    className="rounded-lg border border-ivory-300 bg-ivory-50/70 p-3 text-xs flex items-center justify-between group hover:border-brand-600 hover:bg-white transition-all dark:border-night-700 dark:bg-night-900 dark:hover:bg-night-800"
                    onClick={() => {
                      setInput(s);
                      send(s);
                    }}
                  >
                    <span className="text-pine-800 dark:text-pine-200 font-medium">{s}</span>
                    <Send size={12} className="text-brand-700 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Messages */}
          {msgs.map((m) => {
            const isUser = m.role === "user";
            const records = m.records ?? [];
            const hasNumeric = records.filter((r) => typeof r.value === "number").length > 0;
            const viewMode = viewModes[m.id] ?? "table";

            return (
              <div
                key={m.id}
                className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}
              >
                {!isUser && (
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-800 text-white shadow-subtle mt-0.5">
                    <Bot size={15} />
                  </div>
                )}

                <div
                  className={`max-w-full sm:max-w-[85%] rounded-xl p-4 shadow-subtle ${
                    isUser
                      ? "bg-brand-800 text-white rounded-br-none"
                      : "border border-ivory-300 bg-white dark:border-night-700 dark:bg-night-900 rounded-bl-none text-pine-900 dark:text-pine-100"
                  }`}
                >
                  {m.error ? (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2 text-alert-error font-medium text-xs">
                        <AlertCircle size={15} />
                        {m.error}
                      </div>
                      {m.retry && (
                        <button
                          className="btn-o text-xs py-1 px-2.5 mt-2"
                          onClick={() => send(m.retry!, true)}
                        >
                          <RotateCw size={12} /> Retry query
                        </button>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-3 min-w-0">
                      {m.label && (
                        <div className="flex flex-wrap items-center gap-2">
                          <div
                            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-bold tracking-wide uppercase border ${
                              m.inference_mode === "model-generated" || (m.answer_type === "ai_generated" && !m.fallback_used)
                                ? "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800"
                                : m.fallback_used
                                ? "bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800"
                                : m.inference_mode === "verified-scheme"
                                ? "bg-blue-50 text-blue-800 border-blue-200 dark:bg-blue-950/60 dark:text-blue-300 dark:border-blue-800"
                                : "bg-ivory-100 text-pine-700 border-ivory-200 dark:bg-night-800 dark:text-brand-300 dark:border-night-700"
                            }`}
                          >
                            {m.inference_mode === "model-generated" || (m.answer_type === "ai_generated" && !m.fallback_used) ? (
                              <Sparkles size={11} className="text-emerald-600 dark:text-emerald-400" />
                            ) : (
                              <Database size={11} />
                            )}
                            {m.label}
                          </div>
                          {m.fallback_reason && (
                            <span className="text-[10px] text-amber-700 dark:text-amber-400 font-medium">
                              ({m.fallback_reason})
                            </span>
                          )}
                        </div>
                      )}

                      {isUser ? (
                        <p className="whitespace-pre-wrap text-xs sm:text-sm leading-relaxed">{m.text}</p>
                      ) : (
                        <FormattedMessage content={m.text} />
                      )}

                      {/* Supporting Evidence Container */}
                      {records.length > 0 && (
                        <div className="mt-4 pt-3 border-t border-ivory-200 dark:border-night-750 space-y-3">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold text-pine-900 dark:text-white flex items-center gap-1.5">
                              <Database size={13} className="text-brand-700 dark:text-brand-400" />
                              Supporting Records ({records.length})
                            </span>

                            {hasNumeric && (
                              <div className="flex rounded-md border border-ivory-300 p-0.5 text-xs dark:border-night-700 bg-ivory-50 dark:bg-night-800">
                                <button
                                  className={`flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium transition ${
                                    viewMode === "table"
                                      ? "bg-white text-pine-900 shadow-subtle dark:bg-night-700 dark:text-white font-semibold"
                                      : "muted hover:text-pine-900 dark:hover:text-white"
                                  }`}
                                  onClick={() =>
                                    setViewModes((p) => ({ ...p, [m.id]: "table" }))
                                  }
                                >
                                  <TableIcon size={12} /> Table
                                </button>
                                <button
                                  className={`flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium transition ${
                                    viewMode === "chart"
                                      ? "bg-white text-pine-900 shadow-subtle dark:bg-night-700 dark:text-white font-semibold"
                                      : "muted hover:text-pine-900 dark:hover:text-white"
                                  }`}
                                  onClick={() =>
                                    setViewModes((p) => ({ ...p, [m.id]: "chart" }))
                                  }
                                >
                                  <BarChart2 size={12} /> Chart
                                </button>
                              </div>
                            )}
                          </div>

                          <div className="w-full min-w-0 overflow-hidden">
                            {viewMode === "chart" && hasNumeric ? (
                              <div className="rounded-lg border border-ivory-200 p-3 bg-ivory-50/50 dark:border-night-700 dark:bg-night-850 min-h-[240px]">
                                <CompareBar records={records} height={220} />
                              </div>
                            ) : (
                              <RecordsTable records={records} max={8} />
                            )}
                          </div>
                        </div>
                      )}

                      {/* Evidence Summary Ribbon */}
                      {m.evidence_summary && (
                        <div className="rounded-lg bg-ivory-100/80 p-2.5 text-xs border border-ivory-200 dark:border-night-700 dark:bg-night-800 space-y-1">
                          <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono">
                            <span className="text-pine-700 dark:text-pine-300 font-semibold">
                              Verified: <b>{m.evidence_summary.record_count}</b> observation(s)
                            </span>
                            {m.evidence_summary.statistics && (
                              <span className="text-brand-800 dark:text-brand-400">
                                Mean: <b>{m.evidence_summary.statistics.mean}</b> (Min: {m.evidence_summary.statistics.min}, Max: {m.evidence_summary.statistics.max})
                              </span>
                            )}
                          </div>
                          <div className="text-[10px] muted">
                            {m.evidence_summary.methodology}
                          </div>
                        </div>
                      )}

                      {/* Clickable Research Follow-ups */}
                      {m.follow_ups && m.follow_ups.length > 0 && (
                        <div className="pt-2 border-t border-ivory-200 dark:border-night-750 space-y-1.5">
                          <span className="text-[10px] uppercase font-bold tracking-wider muted block">
                            Suggested Research Inquiries:
                          </span>
                          <div className="flex flex-wrap gap-1.5">
                            {m.follow_ups.map((fu, idx) => (
                              <button
                                key={idx}
                                onClick={() => {
                                  setInput(fu);
                                  send(fu);
                                }}
                                className="chip py-1 px-2.5 text-[11px] hover:border-brand-500 hover:text-brand-900"
                              >
                                <span>{fu}</span>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {isUser && (
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-pine-800 text-white shadow-subtle mt-0.5">
                    <User size={15} />
                  </div>
                )}
              </div>
            );
          })}

          {busy && (
            <div className="flex gap-2.5 items-center text-xs muted pl-11 py-2">
              <Loader2 className="animate-spin text-brand-700" size={15} />
              Searching public health records & grounding response…
            </div>
          )}
          <div ref={endRef} />
        </div>

        {/* Message Input Composer */}
        <div className="border-t border-ivory-200 bg-white/95 dark:border-night-750 dark:bg-night-850/95 pt-3 mt-2 shrink-0">
          <div className="flex items-center gap-2">
            <input
              className="input flex-1 py-2 text-xs sm:text-sm"
              value={input}
              maxLength={500}
              placeholder="Ask about a health indicator (e.g. 'institutional births in Kerala')…"
              aria-label="Your health data question"
              disabled={busy}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
            />
            <button
              className="btn px-4 py-2 shrink-0"
              onClick={() => send(input)}
              disabled={busy || input.trim().length < 3}
              aria-label="Send query"
            >
              {busy ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
              <span className="hidden sm:inline">Send</span>
            </button>
          </div>
          <div className="flex justify-between items-center text-[10px] muted px-1 pt-1.5">
            <span>Press Enter to send</span>
            <span className="font-mono">{input.length}/500</span>
          </div>
        </div>
      </section>
    </div>
  );
}

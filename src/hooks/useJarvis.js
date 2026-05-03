/* src/hooks/useJarvis.js
 * Backend client for Friday: chat (SSE), confirm action, mode switch,
 * news, ideas, document/github analysis, daily context, friend profile.
 */
import { useCallback, useRef, useState } from "react";

export function useJarvisAPI({
  apiBase = "http://localhost:8000",
  userId = "anonymous",
  jarvisName = "Friday",
  userName = "Mr Vijesh",
} = {}) {
  const [streaming, setStreaming] = useState(false);
  const [pendingAction, setPendingAction] = useState(null);
  const [mode, setMode] = useState("friend");
  const conversationIdRef = useRef(null);

  const chat = useCallback(async (message, { onDelta, onDone, onError, modeOverride } = {}) => {
    setStreaming(true);
    try {
      const r = await fetch(`${apiBase}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          jarvis_name: jarvisName,
          user_name: userName,
          message,
          conversation_id: conversationIdRef.current,
          mode: modeOverride || mode,
        }),
      });
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buf = "", full = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop();
        for (const part of parts) {
          if (!part.startsWith("data:")) continue;
          try {
            const obj = JSON.parse(part.slice(5).trim());
            if (obj.delta) { full += obj.delta; onDelta?.(obj.delta, full); }
            if (obj.done) {
              conversationIdRef.current = obj.conversation_id || conversationIdRef.current;
              if (obj.mode) setMode(obj.mode);
              if (obj.requires_confirmation) setPendingAction(obj);
              onDone?.(full, obj);
            }
            if (obj.error) onError?.(obj.error);
          } catch { /* ignore parse errors */ }
        }
      }
      return full;
    } catch (e) {
      onError?.(String(e));
      return "";
    } finally {
      setStreaming(false);
    }
  }, [apiBase, userId, jarvisName, userName, mode]);

  const confirmAction = useCallback(async (actionId, confirm) => {
    setPendingAction(null);
    const r = await fetch(`${apiBase}/computer/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action_id: actionId, confirm }),
    });
    return await r.json();
  }, [apiBase]);

  const executeComputer = useCallback(async (naturalCommand, { requireConfirmation = true } = {}) => {
    const r = await fetch(`${apiBase}/computer/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: userId,
        natural_command: naturalCommand,
        require_confirmation: requireConfirmation,
      }),
    });
    const data = await r.json();
    if (data.requires_confirmation) setPendingAction(data);
    return data;
  }, [apiBase, userId]);

  const switchMode = useCallback((newMode) => setMode(newMode), []);

  const triggerMorningBriefing = useCallback(async () => {
    const r = await fetch(`${apiBase}/news/morning-brief/${userId}`);
    return await r.json();
  }, [apiBase, userId]);

  const triggerNewsQuery = useCallback(async (query) => {
    const r = await fetch(`${apiBase}/news/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, query }),
    });
    return await r.json();
  }, [apiBase, userId]);

  const generateIdeas = useCallback(async (topic, modeName = "viral", count = 5) => {
    const r = await fetch(`${apiBase}/ideas/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, topic, mode: modeName, count }),
    });
    return await r.json();
  }, [apiBase, userId]);

  const evaluateIdea = useCallback(async (idea) => {
    const r = await fetch(`${apiBase}/ideas/evaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, idea }),
    });
    return await r.json();
  }, [apiBase, userId]);

  const analyzeDocument = useCallback(async (file) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("user_id", userId);
    const r = await fetch(`${apiBase}/analyze/document`, {
      method: "POST", body: fd,
    });
    return await r.json();
  }, [apiBase, userId]);

  const analyzeGithub = useCallback(async (url) => {
    const r = await fetch(`${apiBase}/analyze/github`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, url }),
    });
    return await r.json();
  }, [apiBase, userId]);

  const saveDailyContext = useCallback(async (context) => {
    const r = await fetch(`${apiBase}/daily-context`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, ...context }),
    });
    return await r.json();
  }, [apiBase, userId]);

  return {
    chat, streaming, mode, switchMode,
    pendingAction, setPendingAction, confirmAction,
    executeComputer,
    triggerMorningBriefing, triggerNewsQuery,
    generateIdeas, evaluateIdea,
    analyzeDocument, analyzeGithub,
    saveDailyContext,
    conversationIdRef,
  };
}

export default useJarvisAPI;


// ───────────── Named-function helpers used elsewhere ─────────────
export const API_BASE = "http://localhost:8000";

export async function health() {
  try {
    const r = await fetch(`${API_BASE}/health`);
    return await r.json();
  } catch { return { ok: false }; }
}

export async function getAboutMe(userId) {
  if (!userId) return {};
  try {
    const r = await fetch(`${API_BASE}/about-me/${userId}`);
    return await r.json();
  } catch { return {}; }
}

export async function saveAboutMe(payload) {
  try {
    const r = await fetch(`${API_BASE}/about-me`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return await r.json();
  } catch { return {}; }
}

export async function research(payload) {
  try {
    const r = await fetch(`${API_BASE}/research`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return await r.json();
  } catch { return {}; }
}

export async function generateIdeas(payload) {
  try {
    const r = await fetch(`${API_BASE}/ideas/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return await r.json();
  } catch { return { ideas: [] }; }
}

export async function evaluateIdea(payload) {
  try {
    const r = await fetch(`${API_BASE}/ideas/evaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return await r.json();
  } catch { return {}; }
}

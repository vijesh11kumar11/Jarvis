/* src/components/UploadBar.jsx
 * Floating drop-zone for documents + GitHub URL.
 * - Drag a file here, OR paste a GitHub URL — Friday analyzes and speaks back.
 */
import React, { useCallback, useState } from "react";
import { motion } from "framer-motion";
import { useJarvis } from "../context/JarvisContext.jsx";
import { useJarvisAPI } from "../hooks/useJarvis.js";

const GH_RE = /github\.com\/[\w.-]+\/[\w.-]+/i;

export default function UploadBar({ onAnalysis }) {
  const { profile } = useJarvis();
  const api = useJarvisAPI({
    userId: profile?.userId || "anonymous",
    jarvisName: profile.jarvisName,
    userName: profile.userName,
  });
  const [busy, setBusy] = useState(false);
  const [hover, setHover] = useState(false);
  const [pasted, setPasted] = useState("");

  const handleFile = useCallback(async (file) => {
    if (!file) return;
    setBusy(true);
    try {
      const result = await api.analyzeDocument(file);
      onAnalysis?.(result);
    } finally {
      setBusy(false);
    }
  }, [api, onAnalysis]);

  const handleUrl = useCallback(async (url) => {
    if (!url) return;
    setBusy(true);
    try {
      const result = await api.analyzeGithub(url);
      onAnalysis?.({ ...result, spoken: result?.spoken });
    } finally {
      setBusy(false);
      setPasted("");
    }
  }, [api, onAnalysis]);

  const onDrop = (e) => {
    e.preventDefault(); setHover(false);
    const f = e.dataTransfer?.files?.[0];
    if (f) handleFile(f);
    else {
      const txt = e.dataTransfer?.getData("text/plain") || "";
      if (GH_RE.test(txt)) handleUrl(txt);
    }
  };

  const onPaste = (e) => {
    const txt = e.clipboardData?.getData("text") || "";
    if (GH_RE.test(txt)) {
      e.preventDefault();
      setPasted(txt);
      handleUrl(txt);
    }
  };

  return (
    <motion.label
      onDragOver={(e) => { e.preventDefault(); setHover(true); }}
      onDragLeave={() => setHover(false)}
      onDrop={onDrop}
      onPaste={onPaste}
      tabIndex={0}
      className={`flex flex-col items-center justify-center rounded-xl
                  border-2 border-dashed cursor-pointer text-xs
                  transition-colors backdrop-blur-md
                  ${hover ? "bg-violet-500/20 border-violet-300" :
                            "bg-black/40 border-white/15 hover:border-violet-400/60"}`}
      style={{ width: 200, height: 110 }}
      animate={{ scale: hover ? 1.03 : 1 }}
    >
      <input type="file"
        accept=".pdf,.docx,.txt,.md,.csv,.json,.pptx,.png,.jpg,.jpeg,.webp"
        className="hidden"
        onChange={(e) => handleFile(e.target.files?.[0])} />
      <div className="text-violet-200/90 text-center px-3">
        {busy ? "Analyzing…" :
          <>📎 Drop file or paste GitHub URL<br/>
          <span className="opacity-60">Friday will read it & speak</span></>}
      </div>
      {pasted && (
        <div className="text-[10px] mt-1 text-emerald-300 truncate w-full px-2">
          {pasted}
        </div>
      )}
    </motion.label>
  );
}

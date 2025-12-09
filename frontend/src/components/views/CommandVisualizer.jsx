import React, { useState, useEffect } from "react";

export default function CommandVisualizer({ wsData }) {
  const [commands, setCommands] = useState([]);
  const [liveText, setLiveText] = useState("");
  const [activeKey, setActiveKey] = useState(null);

  const keyboard = [
    ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"],
    ["Tab", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "Backspace"],
    ["Caps", "A", "S", "D", "F", "G", "H", "J", "K", "L", "Enter"],
    ["Shift", "Z", "X", "C", "V", "B", "N", "M", "Shift"],
    ["Ctrl", "Alt", "SPACE", "Alt", "Ctrl"],
  ];

  useEffect(() => {
    if (!wsData) return;

    try {
      const parsed = JSON.parse(wsData.data);
      if (parsed.type !== "command") return;

      const cmd = { ...parsed, id: Date.now() };
      setCommands((prev) => [cmd, ...prev].slice(0, 20));

      setActiveKey(parsed.command);
      setTimeout(() => setActiveKey(null), 300);

      // Live text logic
      if (parsed.command === "ENTER") {
        // Enter action (optional)
      } else if (parsed.command === "BACKSPACE") {
        setLiveText((prev) => prev.slice(0, -1));
      } else {
        setLiveText((prev) => prev + parsed.command);
      }
    } catch (e) {
      console.error("Command parse error:", e);
    }
  }, [wsData]);

  return (
    <div className="space-y-4">

      {/* -------------------- MAIN PANEL -------------------- */}
      <div className="bg-surface rounded-lg shadow-card p-6">
        <h2 className="text-2xl font-bold text-text mb-4">
          Command Recognition
        </h2>

        {/* Live Text */}
        <div className="bg-bg rounded-lg p-4 mb-4">
          <div className="text-sm text-muted mb-2">Live Text Preview:</div>
          <div className="text-2xl font-mono min-h-[3rem] bg-surface rounded p-3 text-text border border-border">
            {liveText || <span className="text-muted/50">Waiting for input...</span>}
          </div>
        </div>

        {/* -------------------- KEYBOARD -------------------- */}
        <div className="space-y-2 mb-4">
          {keyboard.map((row, i) => (
            <div key={i} className="flex justify-center gap-2">
              {row.map((key) => {
                const IS_SPACE = key === "SPACE";
                const IS_WIDE =
                  ["Tab", "Backspace", "Caps", "Enter", "Shift"].includes(key);
                const IS_EXTRA_WIDE = key === "SPACE";

                const sizeClasses = IS_EXTRA_WIDE
                  ? "px-24"
                  : IS_WIDE
                    ? "px-10"
                    : "w-12";

                const isActive = activeKey === key;
                return (
                  <div
                    key={key}
                    className={`command-key ${sizeClasses} h-12 flex items-center justify-center rounded-lg border-2 font-semibold transition-all
                      ${isActive
                        ? "bg-primary border-primary text-primary-contrast scale-110"
                        : "border-border bg-surface text-text"
                      }`}
                  >
                    {IS_SPACE ? "Space" : key}
                  </div>
                );
              })}
            </div>
          ))}

          {/* BACKSPACE + ENTER */}
          <div className="flex justify-center gap-2 mt-4">
            <div
              className={`command-key px-6 h-12 flex items-center justify-center rounded-lg border-2 font-semibold transition-all
                ${activeKey === "BACKSPACE"
                  ? "bg-primary border-primary text-primary-contrast scale-110"
                  : "border-border bg-surface text-text"
                }`}
            >
              ⌫ BACK
            </div>

            <div
              className={`command-key px-12 h-12 flex items-center justify-center rounded-lg border-2 font-semibold transition-all
                ${activeKey === "ENTER"
                  ? "bg-accent border-accent text-primary-contrast scale-110"
                  : "border-border bg-surface text-text"
                }`}
            >
              ↵ ENTER
            </div>
          </div>
        </div>
      </div>

      {/* -------------------- COMMAND FEED -------------------- */}
      <div className="bg-surface rounded-lg shadow-card p-6">
        <h3 className="text-lg font-semibold text-text mb-4">
          Command Timeline
        </h3>

        <div className="space-y-2 max-h-64 overflow-y-auto scrollbar-hide">
          {commands.length === 0 ? (
            <p className="text-muted text-center py-8">
              Waiting for recognized commands...
            </p>
          ) : (
            commands.map((cmd) => (
              <div
                key={cmd.id}
                className="flex items-center justify-between p-3 bg-bg rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <span className="text-2xl font-bold text-primary">
                    {cmd.command}
                  </span>
                  <span className="text-sm text-muted">
                    {new Date(cmd.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <div className="text-sm font-medium text-text">
                  {(cmd.confidence * 100).toFixed(1)}%
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

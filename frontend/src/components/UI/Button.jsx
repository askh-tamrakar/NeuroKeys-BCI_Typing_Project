import React from "react";

export default function Button({ children, onClick, variant = "default", className = "" }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1 rounded ${
        variant === "ghost" ? "bg-transparent" : "bg-slate-700"
      } ${className}`}
    >
      {children}
    </button>
  );
}

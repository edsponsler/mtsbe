"use client";

import React, { useState } from "react";

interface ExpandableTextProps {
  text: string;
  initialClamp?: number;
  className?: string;
}

export function ExpandableText({
  text,
  initialClamp = 4,
  className = "source-text",
}: ExpandableTextProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  // Estimate threshold: if text is longer than 160 chars, show the expansion toggle
  const isLong = text && text.trim().length > 160;

  return (
    <div className="expandable-text-container">
      <p
        className={`${className} ${isExpanded ? "expanded" : ""}`}
        style={
          isExpanded
            ? {
                WebkitLineClamp: "unset",
                display: "block",
                overflow: "visible",
              }
            : initialClamp !== 4
            ? { WebkitLineClamp: initialClamp }
            : undefined
        }
      >
        {text}
      </p>
      {isLong && (
        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="expand-text-btn"
          aria-expanded={isExpanded}
        >
          {isExpanded ? (
            <>
              <span>Collapse English Text</span>
              <span className="expand-arrow">▲</span>
            </>
          ) : (
            <>
              <span>View Full English Text</span>
              <span className="expand-arrow">▼</span>
            </>
          )}
        </button>
      )}
    </div>
  );
}

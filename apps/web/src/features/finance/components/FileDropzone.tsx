"use client";

import { FileText, UploadCloud, X } from "lucide-react";
import { useRef, useState } from "react";

type Props = {
  file: File | null;
  onFile: (file: File) => void;
  onClear: () => void;
  disabled?: boolean;
};

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function FileDropzone({ file, onFile, onClear, disabled = false }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

  const acceptFile = (candidate?: File) => {
    if (!candidate || disabled || !candidate.name.toLowerCase().endsWith(".pdf")) return;
    onFile(candidate);
  };

  if (file) {
    return (
      <div className="selected-file">
        <span className="selected-file__icon"><FileText size={20} /></span>
        <div className="selected-file__content">
          <strong>{file.name}</strong>
          <span>{formatBytes(file.size)} · Documento PDF</span>
        </div>
        <button className="icon-button" onClick={onClear} disabled={disabled} aria-label="Quitar PDF">
          <X size={18} />
        </button>
      </div>
    );
  }

  return (
    <div
      className={`dropzone${dragActive ? " is-dragging" : ""}`}
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(event) => {
        if (!disabled && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          inputRef.current?.click();
        }
      }}
      onDragEnter={(event) => { event.preventDefault(); if (!disabled) setDragActive(true); }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={(event) => { event.preventDefault(); setDragActive(false); }}
      onDrop={(event) => {
        event.preventDefault();
        setDragActive(false);
        acceptFile(event.dataTransfer.files[0]);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        hidden
        disabled={disabled}
        onChange={(event) => acceptFile(event.target.files?.[0])}
      />
      <span className="dropzone__icon"><UploadCloud size={26} /></span>
      <strong>Arrastra una factura aquí</strong>
      <span>o selecciónala desde tu equipo</span>
      <small>PDF · Máximo 15 MB · Una factura por sesión</small>
    </div>
  );
}



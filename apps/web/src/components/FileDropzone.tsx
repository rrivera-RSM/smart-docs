"use client";

import { useRef, useState } from "react";
import { FileText, UploadCloud, X } from "lucide-react";

type Props = {
  file: File | null;
  onFile: (file: File) => void;
  onClear?: () => void;
  disabled?: boolean;
  title?: string;
  description?: string;
  acceptedExtensions?: string[];
  formatHint?: string;
};

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return Math.max(1, Math.round(bytes / 1024)) + " KB";
  }
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

export function FileDropzone({
  file,
  onFile,
  onClear,
  disabled = false,
  title = "Arrastra tu documento aquí",
  description = "o selecciónalo desde tu equipo",
  acceptedExtensions = [".docx"],
  formatHint = "DOCX",
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

  const acceptFile = (candidate?: File) => {
    if (!candidate || disabled) return;
    if (
      !acceptedExtensions.some((extension) =>
        candidate.name.toLowerCase().endsWith(extension),
      )
    ) return;
    onFile(candidate);
  };

  const selectedFormat = file?.name.split(".").pop()?.toUpperCase() ?? "Documento";

  if (file) {
    return (
      <div className="selected-file">
        <span className="selected-file__icon">
          <FileText size={20} aria-hidden="true" />
        </span>
        <div className="selected-file__content">
          <strong>{file.name}</strong>
          <span>{formatBytes(file.size)} · {selectedFormat}</span>
        </div>
        {onClear && (
          <button
            type="button"
            className="icon-button"
            onClick={onClear}
            aria-label="Quitar documento"
            disabled={disabled}
          >
            <X size={18} aria-hidden="true" />
          </button>
        )}
      </div>
    );
  }

  return (
    <div
      className={"dropzone" + (dragActive ? " is-dragging" : "")}
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
      onDragEnter={(event) => {
        event.preventDefault();
        if (!disabled) setDragActive(true);
      }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={(event) => {
        event.preventDefault();
        setDragActive(false);
      }}
      onDrop={(event) => {
        event.preventDefault();
        setDragActive(false);
        acceptFile(event.dataTransfer.files[0]);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept={acceptedExtensions.join(",")}
        hidden
        disabled={disabled}
        onChange={(event) => acceptFile(event.target.files?.[0])}
      />
      <span className="dropzone__icon">
        <UploadCloud size={25} strokeWidth={1.8} aria-hidden="true" />
      </span>
      <strong>{title}</strong>
      <span>{description}</span>
      <small>{formatHint} · Máximo 15 MB</small>
    </div>
  );
}

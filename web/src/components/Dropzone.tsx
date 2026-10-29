import { useRef, useState, type DragEvent } from "react";
import { UploadCloud } from "lucide-react";
import { cx } from "./ui";

interface Props {
  onFiles: (files: File[]) => void;
  extensions: string[];
  maxMb: number;
  multiple?: boolean;
  disabled?: boolean;
  compact?: boolean;
  title?: string;
}

export default function Dropzone({ onFiles, extensions, maxMb, multiple, disabled, compact, title }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const depth = useRef(0);

  const accept = extensions.map((e) => `.${e}`).join(",");

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    depth.current = 0;
    setOver(false);
    if (disabled) return;
    const files = Array.from(e.dataTransfer.files);
    if (files.length) onFiles(multiple ? files : files.slice(0, 1));
  };

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      aria-label={title ?? "Upload media"}
      onClick={() => !disabled && input.current?.click()}
      onKeyDown={(e) => {
        if ((e.key === "Enter" || e.key === " ") && !disabled) {
          e.preventDefault();
          input.current?.click();
        }
      }}
      onDragEnter={(e) => {
        e.preventDefault();
        depth.current++;
        setOver(true);
      }}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={() => {
        depth.current--;
        if (depth.current <= 0) setOver(false);
      }}
      onDrop={handleDrop}
      className={cx(
        "group relative flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed text-center transition-colors",
        compact ? "px-6 py-8" : "px-6 py-14 sm:py-20",
        over ? "border-accent bg-accent-soft" : "border-line-strong bg-surface hover:border-accent hover:bg-surface-2",
        disabled && "pointer-events-none opacity-60",
      )}
    >
      <div
        className={cx(
          "mb-4 grid size-14 place-items-center rounded-2xl transition-colors",
          over ? "bg-accent text-accent-ink" : "bg-accent-soft text-accent group-hover:bg-accent group-hover:text-accent-ink",
        )}
      >
        <UploadCloud className="size-7" aria-hidden />
      </div>
      <p className="text-base font-semibold text-ink">
        {over ? "Drop to analyze" : (title ?? (multiple ? "Drop files here or browse" : "Drop a file here or browse"))}
      </p>
      <p className="mt-1.5 text-sm text-ink-2">
        Images and videos up to {maxMb} MB{multiple ? " each" : ""}
      </p>
      <p className="mt-3 max-w-md text-xs text-ink-3">{extensions.map((e) => e.toUpperCase()).join(" · ")}</p>
      <input
        ref={input}
        type="file"
        className="hidden"
        accept={accept}
        multiple={multiple}
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          e.target.value = "";
          if (files.length) onFiles(files);
        }}
      />
    </div>
  );
}

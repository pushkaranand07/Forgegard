// Small JPEG previews for history and printed reports. Failures resolve to
// undefined — a missing thumbnail must never block an analysis.

const MAX_EDGE = 320;

function drawToDataUrl(source: CanvasImageSource, w: number, h: number): string | undefined {
  const scale = Math.min(1, MAX_EDGE / Math.max(w, h));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(w * scale));
  canvas.height = Math.max(1, Math.round(h * scale));
  const ctx = canvas.getContext("2d");
  if (!ctx) return undefined;
  ctx.drawImage(source, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.72);
}

function imageThumbnail(url: string): Promise<string | undefined> {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(drawToDataUrl(img, img.naturalWidth, img.naturalHeight));
    img.onerror = () => resolve(undefined);
    img.src = url;
  });
}

function videoThumbnail(url: string): Promise<string | undefined> {
  return new Promise((resolve) => {
    const video = document.createElement("video");
    const done = (v: string | undefined) => {
      clearTimeout(timer);
      video.removeAttribute("src");
      video.load();
      resolve(v);
    };
    const timer = setTimeout(() => done(undefined), 6000);
    video.muted = true;
    video.preload = "auto";
    video.playsInline = true;
    video.onloadedmetadata = () => {
      video.currentTime = Math.min(1, (video.duration || 0) * 0.1);
    };
    video.onseeked = () => done(drawToDataUrl(video, video.videoWidth, video.videoHeight));
    video.onerror = () => done(undefined);
    video.src = url;
  });
}

export async function makeThumbnail(file: File): Promise<string | undefined> {
  const url = URL.createObjectURL(file);
  try {
    if (file.type.startsWith("video/") || /\.(mp4|webm|mov|mkv|avi|3gp|flv|wmv)$/i.test(file.name)) {
      return await videoThumbnail(url);
    }
    return await imageThumbnail(url);
  } catch {
    return undefined;
  } finally {
    URL.revokeObjectURL(url);
  }
}

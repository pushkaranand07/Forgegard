import { useNavigate } from "react-router-dom";
import { ArrowRight, FileStack, FileText, Fingerprint, ImageIcon, ScanFace } from "lucide-react";
import Dropzone from "../components/Dropzone";
import HistoryRow from "../components/HistoryRow";
import { ButtonLink, Card, SectionTitle } from "../components/ui";
import { useHealth } from "../hooks/useHealth";
import { handOffFile } from "../lib/handoff";
import { useHistory } from "../lib/history";

const FEATURES = [
  {
    icon: ImageIcon,
    title: "Image tamper detection",
    body: "Two-level analysis: metadata forensics flags editing software, and error-level analysis with a CNN finds spliced or retouched regions.",
  },
  {
    icon: ScanFace,
    title: "Video deepfake detection",
    body: "Samples 32 frames, isolates faces with MTCNN and scores each one with a pretrained EfficientNet-B7 face-swap classifier from the DFDC 1st-place solution.",
  },
  {
    icon: FileStack,
    title: "Batch screening",
    body: "Queue a mix of images and videos in one request and get a sortable results table you can export to CSV.",
  },
  {
    icon: FileText,
    title: "Printable reports",
    body: "Every analysis produces a clean, paginated report — print it or save it as a PDF to attach to a case file.",
  },
];

const STEPS = [
  { n: "01", title: "Upload", body: "Drop an image or video. Nothing leaves your ForgeGuard server." },
  { n: "02", title: "Analyze", body: "The matching model runs automatically — seconds for images, under a minute for most videos." },
  { n: "03", title: "Review", body: "Read the verdict, confidence and the evidence behind it, then export or print." },
];

export default function Home() {
  const navigate = useNavigate();
  const { limits } = useHealth();
  const recent = useHistory().slice(0, 4);

  return (
    <div className="space-y-20">
      <section className="grid items-center gap-10 lg:grid-cols-2">
        <div>
          <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-xs font-medium text-ink-2">
            <Fingerprint className="size-3.5 text-accent" aria-hidden />
            AI media forensics
          </p>
          <h1 className="text-4xl font-semibold tracking-tight text-ink sm:text-5xl">
            Know if an image or video has been <span className="text-accent">manipulated</span>.
          </h1>
          <p className="mt-5 max-w-xl text-lg text-ink-2">
            ForgeGuard checks photos for tampering and videos for face deepfakes, and explains what it found in a report
            you can share.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <ButtonLink to="/analyze" size="lg">
              Start an analysis <ArrowRight className="size-4" />
            </ButtonLink>
            <ButtonLink to="/about" size="lg" variant="secondary">
              How it works
            </ButtonLink>
          </div>
        </div>
        <Dropzone
          onFiles={([f]) => {
            handOffFile(f);
            navigate("/analyze");
          }}
          extensions={[...limits.image_extensions, ...limits.video_extensions]}
          maxMb={limits.max_upload_mb}
          title="Drop a file to analyze it now"
        />
      </section>

      {recent.length > 0 && (
        <section>
          <div className="mb-4 flex items-end justify-between">
            <h2 className="text-lg font-semibold text-ink">Recent analyses</h2>
            <ButtonLink to="/history" variant="ghost" size="sm">
              View all <ArrowRight className="size-3.5" />
            </ButtonLink>
          </div>
          <Card className="divide-y divide-line">
            {recent.map((a) => (
              <HistoryRow key={a.id} analysis={a} />
            ))}
          </Card>
        </section>
      )}

      <section>
        <SectionTitle eyebrow="Capabilities" title="Built for verification work">
          Two specialised models behind one upload box, with the evidence laid out so you can judge the result yourself.
        </SectionTitle>
        <div className="grid gap-4 sm:grid-cols-2">
          {FEATURES.map(({ icon: Icon, title, body }) => (
            <Card key={title} className="p-6">
              <div className="mb-4 grid size-10 place-items-center rounded-xl bg-accent-soft text-accent">
                <Icon className="size-5" aria-hidden />
              </div>
              <h3 className="font-semibold text-ink">{title}</h3>
              <p className="mt-1.5 text-sm text-ink-2">{body}</p>
            </Card>
          ))}
        </div>
      </section>

      <section>
        <SectionTitle eyebrow="Workflow" title="Three steps to a verdict" />
        <div className="grid gap-4 md:grid-cols-3">
          {STEPS.map((s) => (
            <div key={s.n} className="border-t-2 border-accent pt-4">
              <p className="font-mono text-sm text-accent">{s.n}</p>
              <h3 className="mt-1 font-semibold text-ink">{s.title}</h3>
              <p className="mt-1 text-sm text-ink-2">{s.body}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

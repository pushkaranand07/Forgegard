import { ArrowRight, Brain, Crop, Film, Layers, Search, Tags } from "lucide-react";
import { ButtonLink, Card, SectionTitle } from "../components/ui";

const IMAGE_STEPS = [
  { icon: Tags, title: "Metadata forensics", body: "Reads the file's EXIF and embedded text for an editing-software signature such as Photoshop or GIMP. A hit means the file was processed — not necessarily altered." },
  { icon: Layers, title: "Error-level analysis", body: "Re-saves the image as JPEG at 90% quality and amplifies the per-pixel difference. Regions pasted in or retouched recompress differently and stand out." },
  { icon: Brain, title: "CNN classification", body: "A compact convolutional network trained on the CASIA tampering dataset classifies the 128×128 error map as authentic or tampered." },
];

const VIDEO_STEPS = [
  { icon: Film, title: "Frame sampling", body: "32 frames are taken at even intervals across the whole clip so short manipulated segments are still represented." },
  { icon: Crop, title: "Face extraction", body: "MTCNN locates the most confidently detected face in each frame and crops it. Videos with no detectable face return Inconclusive rather than a guess." },
  { icon: Search, title: "EfficientNet-B7", body: "Each 380×380 face crop is scored by an EfficientNet-B7 classifier. High resolution lets it pick up the blending seams and texture artefacts of face swaps." },
  { icon: Brain, title: "Aggregation", body: "Per-face scores are combined with a confidence-weighted strategy: a clear majority of strongly fake (or strongly real) faces decides; otherwise the mean is used." },
];

const LIMITS = [
  "The video model judges faces only. Deepfakes that alter the voice, background or body are out of scope.",
  "Re-encoding, heavy compression, screenshots and very low resolution remove the artefacts both models rely on.",
  "Image metadata is easily stripped or forged, so a clean metadata scan is weak evidence of authenticity.",
  "Confidence describes the model's certainty, not the probability that it is right. Treat results as one input to an investigation.",
];

function Steps({ steps }: { steps: typeof IMAGE_STEPS }) {
  return (
    <ol className="grid gap-4 md:grid-cols-2">
      {steps.map(({ icon: Icon, title, body }, i) => (
        <li key={title}>
          <Card className="h-full p-5">
            <div className="mb-3 flex items-center gap-3">
              <span className="grid size-9 place-items-center rounded-lg bg-accent-soft text-accent">
                <Icon className="size-4.5" aria-hidden />
              </span>
              <span className="font-mono text-xs text-ink-3">Step {i + 1}</span>
            </div>
            <h3 className="font-semibold text-ink">{title}</h3>
            <p className="mt-1 text-sm text-ink-2">{body}</p>
          </Card>
        </li>
      ))}
    </ol>
  );
}

export default function About() {
  return (
    <div className="space-y-16">
      <div className="max-w-3xl">
        <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">How ForgeGuard works</h1>
        <p className="mt-4 text-lg text-ink-2">
          ForgeGuard runs two independent detection pipelines behind one upload. The file type decides which one is used,
          and every report shows the evidence each stage produced.
        </p>
      </div>

      <section>
        <SectionTitle eyebrow="Images" title="Tamper detection pipeline">
          Looks for signs that a photo was edited — spliced objects, cloned regions, retouching.
        </SectionTitle>
        <Steps steps={IMAGE_STEPS} />
      </section>

      <section>
        <SectionTitle eyebrow="Videos" title="Deepfake detection pipeline">
          Looks for synthetic or swapped faces produced by deepfake generators.
        </SectionTitle>
        <Steps steps={VIDEO_STEPS} />
      </section>

      <section>
        <SectionTitle eyebrow="Limitations" title="What the results can and can't tell you" />
        <Card className="divide-y divide-line">
          {LIMITS.map((l) => (
            <p key={l} className="p-5 text-sm text-ink-2">
              {l}
            </p>
          ))}
        </Card>
      </section>

      <div className="flex flex-wrap gap-3">
        <ButtonLink to="/analyze" size="lg">
          Analyze a file <ArrowRight className="size-4" />
        </ButtonLink>
        <ButtonLink to="/docs" size="lg" variant="secondary">
          API reference
        </ButtonLink>
      </div>
    </div>
  );
}

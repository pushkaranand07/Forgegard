import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Download, FileQuestion, Printer, Trash2 } from "lucide-react";
import ReportView from "../components/ReportView";
import { Button, ButtonLink, EmptyState } from "../components/ui";
import { downloadJson } from "../lib/download";
import { history, useHistory } from "../lib/history";

export default function Report() {
  const { id } = useParams();
  const navigate = useNavigate();
  const analysis = useHistory().find((a) => a.id === id);

  if (!analysis) {
    return (
      <EmptyState
        icon={<FileQuestion className="size-6" />}
        title="Report not found"
        action={<ButtonLink to="/history">Back to history</ButtonLink>}
      >
        Reports are stored in the browser where the analysis ran. This one may have been deleted or created on another
        device.
      </EmptyState>
    );
  }

  return (
    <>
      <div className="mb-6 no-print">
        <ButtonLink to="/history" variant="ghost" size="sm" className="-ml-3">
          <ArrowLeft className="size-4" /> History
        </ButtonLink>
      </div>
      <ReportView
        analysis={analysis}
        actions={
          <>
            <Button onClick={() => window.print()}>
              <Printer className="size-4" /> Print / Save PDF
            </Button>
            <Button variant="secondary" onClick={() => downloadJson(analysis)}>
              <Download className="size-4" /> Export JSON
            </Button>
            <Button
              variant="danger"
              className="ml-auto"
              onClick={() => {
                if (confirm("Delete this report from history?")) {
                  history.remove(analysis.id);
                  navigate("/history");
                }
              }}
            >
              <Trash2 className="size-4" /> Delete
            </Button>
          </>
        }
      />
    </>
  );
}

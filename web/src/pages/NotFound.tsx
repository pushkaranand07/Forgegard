import { Compass } from "lucide-react";
import { ButtonLink, EmptyState } from "../components/ui";

export default function NotFound() {
  return (
    <EmptyState icon={<Compass className="size-6" />} title="Page not found" action={<ButtonLink to="/">Go home</ButtonLink>}>
      The page you're looking for doesn't exist or has moved.
    </EmptyState>
  );
}

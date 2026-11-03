import { ModelsStateTransition } from "@/components/models-state-transition";

export default function ModelsTemplate({ children }: { children: React.ReactNode }) {
  return <ModelsStateTransition>{children}</ModelsStateTransition>;
}

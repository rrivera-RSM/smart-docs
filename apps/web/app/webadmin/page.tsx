import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { featureFlags } from "@/src/config/featureFlags";
import { WebAdminWorkspace } from "@/src/features/admin/WebAdminWorkspace";

export const metadata: Metadata = {
  title: "WebAdmin",
};

export default function WebAdminPage() {
  if (!featureFlags.webadmin) notFound();
  return <WebAdminWorkspace />;
}

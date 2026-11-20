"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { registerCurrentUser } from "./api/client";

const links = [
  { href: "/finance", label: "Imputación de gastos" },
  { href: "/finance/proveedores", label: "Proveedores" },
  { href: "/finance/webadmin", label: "WebAdmin" },
];

export function FinanceNavigation() {
  const pathname = usePathname();

  useEffect(() => {
    // Access observation is informational; an unavailable registry must not
    // interrupt invoice review. Authentication is owned by SmartDocs.
    void registerCurrentUser().catch(() => undefined);
  }, []);

  return (
    <nav className="finance-nav" aria-label="Imputación de gastos">
      {links.map(({ href, label }) => (
        <Link key={href} href={href} aria-current={pathname === href ? "page" : undefined}>
          {label}
        </Link>
      ))}
    </nav>
  );
}

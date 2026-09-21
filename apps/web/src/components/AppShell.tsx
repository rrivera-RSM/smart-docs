"use client";

import type { PropsWithChildren } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { featureFlags } from "../config/featureFlags";

export function AppShell({ children }: PropsWithChildren) {
  const pathname = usePathname();

  return (
    <div className="app-frame">
      <header className="app-header">
        <div className="app-header__inner">
          <Link className="app-brand" href="/" aria-label="SmartDocs, inicio">
            <img
              src="/logos/corporate/logo_light.svg.svg"
              alt="RSM"
              width="168"
              height="22"
            />
            <span className="app-brand__divider" aria-hidden="true" />
            <span>SmartDocs</span>
          </Link>
          <div className="header-actions">
            <nav className="app-nav" aria-label="Navegación principal">
              <Link
                className={pathname === "/" ? "is-active" : undefined}
                href="/"
                aria-current={pathname === "/" ? "page" : undefined}
              >
                Inicio
              </Link>
              {featureFlags.webadmin && (
                <Link
                  className={pathname === "/webadmin" ? "is-active" : undefined}
                  href="/webadmin"
                  aria-current={pathname === "/webadmin" ? "page" : undefined}
                >
                  WebAdmin
                </Link>
              )}
            </nav>
          </div>
        </div>
      </header>

      <main className="page-shell">{children}</main>

      <footer className="site-footer">
        <span>SmartDocs · Automatización documental</span>
      </footer>
    </div>
  );
}

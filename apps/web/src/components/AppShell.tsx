"use client";

import type { PropsWithChildren } from "react";
import { LogOut, UserRound } from "lucide-react";
import Link from "next/link";
import { signOut, useSession } from "next-auth/react";
import { usePathname } from "next/navigation";

import { featureFlags } from "../config/featureFlags";

export function AppShell({ children }: PropsWithChildren) {
  const pathname = usePathname();
  const { data: session, status } = useSession();
  const userLabel =
    session?.user?.name?.trim() ||
    session?.user?.email?.trim() ||
    "Cuenta RSM";

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
              <Link
                className={pathname.startsWith("/finance") ? "is-active" : undefined}
                href="/finance"
                aria-current={pathname.startsWith("/finance") ? "page" : undefined}
              >
                Imputación de gastos
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
            {status === "authenticated" && (
              <div className="account-summary">
                <UserRound size={16} aria-hidden="true" />
                <span title={userLabel}>{userLabel}</span>
                <button
                  type="button"
                  onClick={() =>
                    signOut({ callbackUrl: "/auth?loggedOut=1" })
                  }
                  aria-label="Cerrar sesión"
                  title="Cerrar sesión"
                >
                  <LogOut size={15} aria-hidden="true" />
                </button>
              </div>
            )}
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

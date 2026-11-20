"use client";

import { Suspense, useEffect, useRef } from "react";
import { signIn } from "next-auth/react";
import { useSearchParams } from "next/navigation";

export default function AuthPage() {
  return (
    <Suspense fallback={<AuthLoading />}>
      <AuthRedirect />
    </Suspense>
  );
}

function AuthRedirect() {
  const started = useRef(false);
  const searchParams = useSearchParams();
  const error = searchParams.get("error");
  const loggedOut = searchParams.get("loggedOut") === "1";

  useEffect(() => {
    if (started.current || error || loggedOut) return;
    started.current = true;

    const callbackUrl = searchParams.get("callbackUrl") ?? "/";
    void signIn("azure-ad", { callbackUrl });
  }, [error, searchParams]);

  return (
    <section className="auth-redirect" aria-live="polite">
      <div className="auth-redirect__card">
        <img
          src="/logos/corporate/logo_light.svg.svg"
          alt="RSM"
          width="168"
          height="22"
        />
        {loggedOut ? (
          <>
            <h1>Sesión cerrada</h1>
            <p>Has salido de SmartDocs correctamente.</p>
            <button
              className="button button--primary"
              onClick={() => signIn("azure-ad", { callbackUrl: "/" })}
            >
              Iniciar sesión
            </button>
          </>
        ) : error ? (
          <>
            <h1>No se ha podido iniciar sesión</h1>
            <p>Azure ha rechazado o interrumpido el acceso.</p>
            <button
              className="button button--primary"
              onClick={() => signIn("azure-ad", { callbackUrl: "/" })}
            >
              Intentar de nuevo
            </button>
          </>
        ) : (
          <>
            <span className="auth-redirect__spinner" aria-hidden="true" />
            <h1>Accediendo a SmartDocs</h1>
            <p>Te estamos redirigiendo a Microsoft para iniciar sesión.</p>
          </>
        )}
      </div>
    </section>
  );
}

function AuthLoading() {
  return (
    <section className="auth-redirect" aria-live="polite">
      <div className="auth-redirect__card">
        <p>Preparando el inicio de sesión…</p>
      </div>
    </section>
  );
}

import type { NextRequest } from "next/server";
import { getToken } from "next-auth/jwt";

import type { AzureJwt } from "@/src/auth/options";

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

const HOP_BY_HOP_HEADERS = [
  "connection",
  "content-length",
  "host",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
];

async function proxyToApi(
  request: NextRequest,
  context: RouteContext,
): Promise<Response> {
  const { path } = await context.params;
  const isHealthCheck = path.length === 1 && path[0] === "health";
  const authEnabled = process.env.SMARTDOCS_AUTH_ENABLED !== "false";
  let accessToken: string | undefined;

  if (authEnabled && !isHealthCheck) {
    const token = (await getToken({
      req: request,
      secret: process.env.NEXTAUTH_SECRET,
    })) as AzureJwt | null;

    if (!token?.accessToken || token.error) {
      return Response.json(
        { detail: "La sesión ha caducado. Vuelve a iniciar sesión." },
        { status: 401 },
      );
    }
    accessToken = token.accessToken;
  }

  const backendBase =
    process.env.SMARTDOCS_API_PROXY_TARGET ?? "http://127.0.0.1:8050";
  const target = new URL(
    `/api/${path.map(encodeURIComponent).join("/")}`,
    backendBase,
  );
  target.search = request.nextUrl.search;

  const headers = new Headers(request.headers);
  for (const header of HOP_BY_HOP_HEADERS) headers.delete(header);
  headers.delete("cookie");
  if (accessToken) headers.set("authorization", `Bearer ${accessToken}`);

  const method = request.method.toUpperCase();
  const response = await fetch(target, {
    method,
    headers,
    body:
      method === "GET" || method === "HEAD"
        ? undefined
        : await request.arrayBuffer(),
    cache: "no-store",
    redirect: "manual",
  });

  const responseHeaders = new Headers(response.headers);
  for (const header of HOP_BY_HOP_HEADERS) responseHeaders.delete(header);

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders,
  });
}

export const dynamic = "force-dynamic";

export const GET = proxyToApi;
export const POST = proxyToApi;
export const PUT = proxyToApi;
export const PATCH = proxyToApi;
export const DELETE = proxyToApi;
export const HEAD = proxyToApi;
export const OPTIONS = proxyToApi;

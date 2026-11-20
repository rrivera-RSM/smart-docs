import type { NextAuthOptions } from "next-auth";
import type { JWT } from "next-auth/jwt";
import AzureADProvider from "next-auth/providers/azure-ad";

export type AzureJwt = JWT & {
  accessToken?: string;
  refreshToken?: string;
  accessTokenExpires?: number;
  error?: "RefreshAccessTokenError";
};

type AzureRefreshResponse = {
  access_token?: string;
  expires_in?: number;
  refresh_token?: string;
};

function apiScope(): string {
  return `api://${process.env.SMARTDOCS_AZURE_API_CLIENT_ID}/user_impersonation`;
}

function requestedScopes(): string {
  return ["openid", "profile", "email", "offline_access", apiScope()].join(
    " ",
  );
}

async function refreshAzureAccessToken(token: AzureJwt): Promise<AzureJwt> {
  try {
    if (!token.refreshToken) {
      throw new Error("Azure AD did not return a refresh token.");
    }

    const tenantId = process.env.SMARTDOCS_AZURE_TENANT_ID;
    const clientId = process.env.SMARTDOCS_AZURE_WEB_CLIENT_ID;
    const clientSecret = process.env.SMARTDOCS_AZURE_WEB_CLIENT_SECRET;
    if (!tenantId || !clientId || !clientSecret) {
      throw new Error("Azure AD authentication is not configured.");
    }

    const response = await fetch(
      `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/token`,
      {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          client_id: clientId,
          client_secret: clientSecret,
          grant_type: "refresh_token",
          refresh_token: token.refreshToken,
          scope: requestedScopes(),
        }),
      },
    );

    const refreshed = (await response.json()) as AzureRefreshResponse;
    if (
      !response.ok ||
      !refreshed.access_token ||
      typeof refreshed.expires_in !== "number"
    ) {
      throw new Error("Azure AD rejected the access token refresh.");
    }

    return {
      ...token,
      accessToken: refreshed.access_token,
      accessTokenExpires: Date.now() + refreshed.expires_in * 1000,
      refreshToken: refreshed.refresh_token ?? token.refreshToken,
      error: undefined,
    };
  } catch {
    return { ...token, error: "RefreshAccessTokenError" };
  }
}

export const authOptions: NextAuthOptions = {
  secret: process.env.NEXTAUTH_SECRET,
  session: { strategy: "jwt" },
  pages: { signIn: "/auth" },
  providers: [
    AzureADProvider({
      clientId: process.env.SMARTDOCS_AZURE_WEB_CLIENT_ID ?? "",
      clientSecret: process.env.SMARTDOCS_AZURE_WEB_CLIENT_SECRET ?? "",
      tenantId: process.env.SMARTDOCS_AZURE_TENANT_ID ?? "",
      authorization: {
        params: { scope: requestedScopes() },
      },
    }),
  ],
  callbacks: {
    async jwt({ token, account }) {
      const azureToken = token as AzureJwt;
      if (account) {
        return {
          ...azureToken,
          accessToken: account.access_token,
          refreshToken: account.refresh_token,
          accessTokenExpires: account.expires_at
            ? account.expires_at * 1000
            : Date.now() + 3600 * 1000,
          error: undefined,
        };
      }

      if (
        azureToken.accessTokenExpires &&
        Date.now() < azureToken.accessTokenExpires - 60_000
      ) {
        return azureToken;
      }

      return refreshAzureAccessToken(azureToken);
    },
    async session({ session }) {
      return session;
    },
  },
};

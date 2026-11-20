import { withAuth } from "next-auth/middleware";

export default withAuth({
  pages: { signIn: "/auth" },
  callbacks: {
    authorized: ({ token }) =>
      process.env.SMARTDOCS_AUTH_ENABLED === "false" || Boolean(token),
  },
});

export const config = {
  matcher: [
    "/((?!api/auth|api/health|auth|_next|favicon.ico|logos/|og.png|rsm_logo.png).*)",
  ],
};

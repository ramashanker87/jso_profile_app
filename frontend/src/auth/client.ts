import { Amplify } from "aws-amplify";
import {
  signIn,
  signUp,
  confirmSignUp,
  resendSignUpCode,
  signInWithRedirect,
  confirmSignIn,
  signOut,
  getCurrentUser,
  fetchAuthSession,
} from "aws-amplify/auth";
import { cognitoUserPoolsTokenProvider } from "aws-amplify/auth/cognito";
import {
  Hub,
  sessionStorage as amplifySessionStorage,
} from "aws-amplify/utils";

export const mockMode = import.meta.env.VITE_USE_MOCK_API === "true";
const localApiMode =
  import.meta.env.DEV && import.meta.env.VITE_USE_LOCAL_API === "true";
const localLogin = mockMode || localApiMode;
const configured =
  !!import.meta.env.VITE_COGNITO_USER_POOL_ID &&
  !!import.meta.env.VITE_COGNITO_CLIENT_ID;
export const googleLoginEnabled =
  !localLogin &&
  configured &&
  import.meta.env.VITE_GOOGLE_LOGIN_ENABLED === "true" &&
  !!import.meta.env.VITE_COGNITO_OAUTH_DOMAIN;
if (!localLogin && configured) {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID,
        userPoolClientId: import.meta.env.VITE_COGNITO_CLIENT_ID,
        ...(googleLoginEnabled
          ? {
              loginWith: {
                oauth: {
                  domain: import.meta.env.VITE_COGNITO_OAUTH_DOMAIN,
                  scopes: ["openid", "email", "profile"],
                  redirectSignIn: [window.location.origin + "/login"],
                  redirectSignOut: [window.location.origin + "/login"],
                  responseType: "code" as const,
                },
              },
            }
          : {}),
      },
    },
  });
  cognitoUserPoolsTokenProvider.setKeyValueStorage(amplifySessionStorage);
}
export interface Challenge {
  step: string;
  attributes?: string[];
}
export async function currentUser(): Promise<string | null> {
  if (localLogin)
    return window.sessionStorage.getItem("profile-library-mock-user");
  if (!configured) return null;
  try {
    const user = await getCurrentUser();
    await accessToken();
    const session = await fetchAuthSession();
    return String(
      session.tokens?.idToken?.payload.email ||
        user.signInDetails?.loginId ||
        user.username,
    );
  } catch {
    return null;
  }
}
export async function login(
  username: string,
  password: string,
): Promise<Challenge | null> {
  if (localLogin) {
    window.sessionStorage.setItem("profile-library-mock-user", username);
    return null;
  }
  if (!configured)
    throw new Error("Login is not configured. Contact your administrator.");
  const result = await signIn({ username, password });
  return result.isSignedIn
    ? null
    : {
        step: result.nextStep.signInStep,
        attributes:
          "missingAttributes" in result.nextStep
            ? result.nextStep.missingAttributes
            : [],
      };
}
export async function challenge(
  answer: string,
  attributes: Record<string, string>,
): Promise<Challenge | null> {
  const result = await confirmSignIn({
    challengeResponse: answer,
    options: { userAttributes: attributes },
  });
  return result.isSignedIn ? null : { step: result.nextStep.signInStep };
}
export async function logout(): Promise<void> {
  if (localLogin) {
    window.sessionStorage.removeItem("profile-library-mock-user");
    return;
  }
  await signOut();
}
export async function accessToken(): Promise<string> {
  if (
    localApiMode &&
    window.sessionStorage.getItem("profile-library-mock-user")
  )
    return "local-dev-token";
  const session = await fetchAuthSession(); // Amplify refreshes expired tokens when possible.
  if (!session.tokens?.accessToken)
    throw new Error("Your session has expired. Please login again.");
  return session.tokens.accessToken.toString();
}

export async function loginWithGoogle(): Promise<void> {
  if (!googleLoginEnabled) throw new Error("Google sign-in is not configured.");
  await signInWithRedirect({ provider: "Google" });
}

export async function hasAppAccess(): Promise<boolean> {
  const group = import.meta.env.VITE_COGNITO_REQUIRED_GROUP;
  if (localLogin || !group) return true;
  const session = await fetchAuthSession();
  const groups = session.tokens?.accessToken?.payload["cognito:groups"];
  return Array.isArray(groups) && groups.includes(group);
}

export function onAuthChange(callback: (failed: boolean) => void): () => void {
  return Hub.listen("auth", ({ payload }) => {
    if (["signedIn", "signedOut", "signInWithRedirect"].includes(payload.event))
      callback(false);
    if (payload.event === "signInWithRedirect_failure") callback(true);
  });
}

export async function registerEmail(
  email: string,
  password: string,
): Promise<boolean> {
  if (localLogin || !configured)
    throw new Error(
      "Email signup is unavailable in demo mode or before configuration.",
    );
  const username = email.trim().toLowerCase();
  const result = await signUp({
    username,
    password,
    options: { userAttributes: { email: username } },
  });
  return result.isSignUpComplete;
}
export async function verifySignup(email: string, code: string): Promise<void> {
  await confirmSignUp({
    username: email.trim().toLowerCase(),
    confirmationCode: code.trim(),
  });
}
export async function resendSignup(email: string): Promise<void> {
  await resendSignUpCode({ username: email.trim().toLowerCase() });
}

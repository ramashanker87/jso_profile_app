import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({
  signup: vi.fn(),
  confirm: vi.fn(),
  resend: vi.fn(),
  configure: vi.fn(),
  redirect: vi.fn(),
  session: vi.fn(),
}));
vi.mock("aws-amplify", () => ({ Amplify: { configure: mocks.configure } }));
vi.mock("aws-amplify/auth", () => ({
  signUp: mocks.signup,
  confirmSignUp: mocks.confirm,
  resendSignUpCode: mocks.resend,
  signIn: vi.fn(),
  confirmSignIn: vi.fn(),
  signOut: vi.fn(),
  getCurrentUser: vi.fn(),
  fetchAuthSession: mocks.session,
  signInWithRedirect: mocks.redirect,
}));
vi.mock("aws-amplify/auth/cognito", () => ({
  cognitoUserPoolsTokenProvider: { setKeyValueStorage: vi.fn() },
}));
vi.mock("aws-amplify/utils", () => ({
  sessionStorage: {},
  Hub: { listen: vi.fn() },
}));
beforeEach(() => {
  vi.resetModules();
  vi.clearAllMocks();
  vi.stubEnv("VITE_USE_MOCK_API", "false");
  vi.stubEnv("VITE_USE_LOCAL_API", "false");
  vi.stubEnv("VITE_COGNITO_USER_POOL_ID", "us-east-1_example");
  vi.stubEnv("VITE_COGNITO_CLIENT_ID", "client");
  vi.stubEnv("VITE_GOOGLE_LOGIN_ENABLED", "true");
  vi.stubEnv(
    "VITE_COGNITO_OAUTH_DOMAIN",
    "example.auth.us-east-1.amazoncognito.com",
  );
  vi.stubEnv("VITE_COGNITO_REQUIRED_GROUP", "profile-library-users");
});
afterEach(() => vi.unstubAllEnvs());
describe("Google authentication", () => {
  it("configures the authorization code flow and sends users to Google", async () => {
    const client = await import("../src/auth/client");
    expect(mocks.configure).toHaveBeenCalledWith(
      expect.objectContaining({
        Auth: {
          Cognito: expect.objectContaining({
            loginWith: {
              oauth: expect.objectContaining({
                responseType: "code",
                domain: "example.auth.us-east-1.amazoncognito.com",
                redirectSignIn: [window.location.origin + "/login"],
                redirectSignOut: [window.location.origin + "/login"],
              }),
            },
          }),
        },
      }),
    );
    await client.loginWithGoogle();
    expect(mocks.redirect).toHaveBeenCalledWith({ provider: "Google" });
  });
  it("does not start Google sign-in until configured", async () => {
    vi.stubEnv("VITE_GOOGLE_LOGIN_ENABLED", "false");
    const client = await import("../src/auth/client");
    expect(client.googleLoginEnabled).toBe(false);
    await expect(client.loginWithGoogle()).rejects.toThrow("not configured");
    expect(mocks.redirect).not.toHaveBeenCalled();
  });
  it("requires the application group, not just a Google provider group", async () => {
    const client = await import("../src/auth/client");
    mocks.session.mockResolvedValue({
      tokens: {
        accessToken: { payload: { "cognito:groups": ["pool_Google"] } },
      },
    });
    expect(await client.hasAppAccess()).toBe(false);
    mocks.session.mockResolvedValue({
      tokens: {
        accessToken: {
          payload: { "cognito:groups": ["profile-library-users"] },
        },
      },
    });
    expect(await client.hasAppAccess()).toBe(true);
  });
});

it("creates and verifies email accounts without granting access or auto-signing in", async () => {
  const client = await import("../src/auth/client");
  mocks.signup.mockResolvedValue({ isSignUpComplete: false });
  expect(
    await client.registerEmail(" Member@Yahoo.com ", "ExamplePass123!"),
  ).toBe(false);
  expect(mocks.signup).toHaveBeenCalledWith({
    username: "member@yahoo.com",
    password: "ExamplePass123!",
    options: { userAttributes: { email: "member@yahoo.com" } },
  });
  await client.verifySignup(" Member@Yahoo.com ", " 123456 ");
  expect(mocks.confirm).toHaveBeenCalledWith({
    username: "member@yahoo.com",
    confirmationCode: "123456",
  });
  await client.resendSignup(" Member@Yahoo.com ");
  expect(mocks.resend).toHaveBeenCalledWith({ username: "member@yahoo.com" });
});

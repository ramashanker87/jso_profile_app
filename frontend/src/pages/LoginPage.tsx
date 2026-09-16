import { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { mockMode, googleLoginEnabled, loginWithGoogle } from "../auth/client";
import type { Challenge } from "../auth/client";
import { LoadingState } from "../components/States";
import { EmailSignup } from "../components/EmailSignup";
import { Logo } from "../components/Logo";
export function LoginPage({ signup = false }: { signup?: boolean }) {
  const auth = useAuth();
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [answer, setAnswer] = useState(""),
    [step, setStep] = useState<Challenge | null>(null),
    [attributes, setAttributes] = useState<Record<string, string>>({}),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  if (auth.loading) return <LoadingState />;
  if (auth.user && auth.authorized) return <Navigate to="/" replace />;
  const newPassword =
    step?.step === "CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED";
  const supported =
    !step ||
    newPassword ||
    [
      "CONFIRM_SIGN_IN_WITH_SMS_CODE",
      "CONFIRM_SIGN_IN_WITH_TOTP_CODE",
      "CONFIRM_SIGN_IN_WITH_EMAIL_CODE",
    ].includes(step.step);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = step
        ? await auth.confirm(answer, attributes)
        : await auth.login(email, password);
      setStep(result);
      setPassword("");
      setAnswer("");
    } catch {
      setError(
        "Unable to login. Check your credentials or contact your administrator.",
      );
    } finally {
      setBusy(false);
    }
  }
  if (auth.user)
    return (
      <main className="login-layout">
        <section className="login-intro">
          <Logo className="login-logo" />
          <h1>Welcome JSO</h1>
        </section>
        <section className="login-form">
          <h2>Awaiting approval</h2>
          <p>
            You are signed in as {auth.user}. An administrator needs to approve
            your access before you can view Members and Idea Incubation.
          </p>
          <p className="muted">Once approved, sign out and sign in again.</p>
          <button onClick={() => void auth.logout()}>Sign out</button>
        </section>
      </main>
    );
  return (
    <main className="login-layout">
      <section className="login-intro">
        <Logo className="login-logo" />
        <span className="eyebrow">JSO COMMUNITY</span>
        <h1>Welcome JSO</h1>
        <p>
          Connect with members.
          <br />
          Be part of our community.
        </p>
      </section>
      <section
        className="login-form"
        aria-label={signup ? "Sign up" : "Log in"}
      >
        {!step && (
          <nav className="auth-switch" aria-label="Account access">
            <Link to="/login" aria-current={!signup ? "page" : undefined}>
              Log in
            </Link>
            <Link to="/signup" aria-current={signup ? "page" : undefined}>
              Sign up
            </Link>
          </nav>
        )}
        <h2>
          {step
            ? newPassword
              ? "Set a new password"
              : "Verify your login"
            : signup
              ? "Create your JSO account"
              : "Welcome back"}
        </h2>
        <p className="muted">
          {signup
            ? "Join JSO with Google or your email and password."
            : "Log in to your JSO account to explore Members and Idea Incubation."}
        </p>
        {mockMode && (
          <p className="notice">
            Local demo · Use any email and password. All profiles are fictional.
          </p>
        )}
        {auth.expired && (
          <p role="alert" className="error">
            Your session has expired. Please login again.
          </p>
        )}
        {auth.authError && (
          <p role="alert" className="error">
            {auth.authError}
          </p>
        )}
        {googleLoginEnabled && !step && (
          <div className="google-signin">
            <button
              type="button"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  await loginWithGoogle();
                } catch {
                  setError("Unable to start Google sign-in. Please try again.");
                  setBusy(false);
                }
              }}
            >
              {busy
                ? "Connecting to Google…"
                : signup
                  ? "Sign up with Google"
                  : "Continue with Google"}
            </button>
            <div className="auth-divider">
              <span>
                {signup ? "or sign up with email" : "or log in with email"}
              </span>
            </div>
          </div>
        )}
        {signup && (
          <div className="signup-info">
            <h3>What happens next?</h3>
            <p>
              Verify your email after creating an account with email and
              password.
            </p>
            <p>
              An administrator will approve your access before you can view
              Members and Idea Incubation.
            </p>
          </div>
        )}
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {(signup || step?.step === "CONFIRM_SIGN_UP") && (
          <EmailSignup
            initialEmail={email}
            verify={!signup}
            onLogin={() => setStep(null)}
          />
        )}
        {!signup && step?.step !== "CONFIRM_SIGN_UP" && (
          <form onSubmit={submit}>
            {!step ? (
              <>
                <label>
                  Email
                  <input
                    type="email"
                    autoComplete="username"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </label>
                <label>
                  Password
                  <input
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </label>
              </>
            ) : supported ? (
              <>
                <label>
                  {newPassword ? "New password" : "Verification code"}
                  <input
                    type={newPassword ? "password" : "text"}
                    autoComplete={
                      newPassword ? "new-password" : "one-time-code"
                    }
                    value={answer}
                    onChange={(e) => setAnswer(e.target.value)}
                    required
                  />
                </label>
                {step.attributes?.map((attr) => (
                  <label key={attr}>
                    {attr}
                    <input
                      value={attributes[attr] || ""}
                      onChange={(e) =>
                        setAttributes({ ...attributes, [attr]: e.target.value })
                      }
                      required
                    />
                  </label>
                ))}
              </>
            ) : (
              <p className="notice">
                Your account requires additional setup. Contact your
                administrator to complete it.
              </p>
            )}
            {supported && (
              <button className="primary" disabled={busy}>
                {busy ? "Logging in…" : step ? "Continue" : "Login"}
              </button>
            )}
          </form>
        )}
        {step && (
          <button
            onClick={() => {
              setStep(null);
              setError("");
            }}
          >
            Start again
          </button>
        )}
        {!step && (
          <p className="auth-footer">
            {signup ? (
              <>
                Already have an account? <Link to="/login">Log in</Link>
              </>
            ) : (
              <>
                New to JSO? <Link to="/signup">Create an account</Link>
              </>
            )}
          </p>
        )}
        {!signup && (
          <p className="muted small">
            Need help signing in? Contact your administrator.
          </p>
        )}
      </section>
    </main>
  );
}

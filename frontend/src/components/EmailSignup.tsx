import { useState } from "react";
import { Link } from "react-router-dom";
import { registerEmail, verifySignup, resendSignup } from "../auth/client";
export function EmailSignup({
  initialEmail = "",
  verify = false,
  onLogin,
}: {
  initialEmail?: string;
  verify?: boolean;
  onLogin?: () => void;
}) {
  const [email, setEmail] = useState(initialEmail);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [code, setCode] = useState("");
  const [phase, setPhase] = useState(verify ? "verify" : "signup");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Unable to complete signup. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  if (phase === "done")
    return (
      <div role="status">
        <h3>Email verified</h3>
        <p>
          Your account is ready for administrator approval. Contact your JSO
          administrator to request access.
        </p>
        <Link to="/login" onClick={onLogin}>
          Continue to login
        </Link>
      </div>
    );
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void run(async () => {
          if (phase === "verify") {
            await verifySignup(email, code);
            setPhase("done");
            return;
          }
          if (password !== confirm) throw new Error("Passwords do not match.");
          const completed = await registerEmail(email, password);
          setPassword("");
          setConfirm("");
          setPhase(completed ? "done" : "verify");
        });
      }}
    >
      {phase === "verify" && (
        <p>
          Enter the verification code sent to your email. Check your spam folder
          too.
        </p>
      )}
      <label>
        Email
        <input
          type="email"
          autoComplete="email"
          value={email}
          disabled={busy}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
      </label>
      {phase === "signup" ? (
        <>
          <label>
            Password
            <input
              type="password"
              autoComplete="new-password"
              minLength={12}
              value={password}
              disabled={busy}
              onChange={(e) => setPassword(e.target.value)}
              required
              aria-describedby="signup-password-help"
            />
          </label>
          <p id="signup-password-help" className="muted small">
            Use at least 12 characters, including uppercase and lowercase
            letters, a number, and a symbol.
          </p>
          <label>
            Confirm password
            <input
              type="password"
              autoComplete="new-password"
              minLength={12}
              value={confirm}
              disabled={busy}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />
          </label>
        </>
      ) : (
        <label>
          Verification code
          <input
            autoComplete="one-time-code"
            value={code}
            disabled={busy}
            onChange={(e) => setCode(e.target.value)}
            required
          />
        </label>
      )}
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      <button className="primary" disabled={busy}>
        {busy
          ? "Please wait…"
          : phase === "signup"
            ? "Create account"
            : "Verify email"}
      </button>
      {phase === "verify" ? (
        <button
          type="button"
          disabled={busy}
          onClick={() =>
            void run(async () => {
              await resendSignup(email);
              setNotice("A new verification code has been sent.");
            })
          }
        >
          Resend code
        </button>
      ) : (
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            setPhase("verify");
            setPassword("");
            setConfirm("");
            setError("");
          }}
        >
          Already have a verification code?
        </button>
      )}
    </form>
  );
}

import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { AuthCard, FormMessage, SubmitButton, TextField } from "../components/auth/AuthCard.tsx";
import { resetPassword } from "../services/auth.ts";
import { ApiError } from "../services/http.ts";

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    setPending(true);
    try {
      await resetPassword(token, password);
      setDone(true);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Unable to reset the password");
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthCard title="Choose a new password">
      {token.length === 0 ? (
        <FormMessage tone="error">This reset link is missing a token.</FormMessage>
      ) : done ? (
        <div className="space-y-4">
          <FormMessage tone="success">Password has been reset.</FormMessage>
          <Link to="/login" className="text-sm font-medium text-emerald-700">
            Sign in
          </Link>
        </div>
      ) : (
        <form className="space-y-4" onSubmit={onSubmit}>
          {error ? <FormMessage tone="error">{error}</FormMessage> : null}
          <TextField
            label="New password"
            type="password"
            value={password}
            autoComplete="new-password"
            onChange={setPassword}
          />
          <TextField
            label="Confirm password"
            type="password"
            value={confirmPassword}
            autoComplete="new-password"
            onChange={setConfirmPassword}
          />
          <SubmitButton pending={pending} label="Update password" />
        </form>
      )}
    </AuthCard>
  );
}

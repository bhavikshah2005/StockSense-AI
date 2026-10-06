import { useState, type FormEvent } from "react";

import { AuthCard, AuthLink, FormMessage, SubmitButton, TextField } from "../components/auth/AuthCard.tsx";
import { forgotPassword } from "../services/auth.ts";
import { ApiError } from "../services/http.ts";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    setPending(true);
    try {
      const result = await forgotPassword(email);
      setMessage(result.detail);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Unable to send reset instructions");
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthCard
      title="Reset your password"
      footer={
        <>
          <AuthLink to="/login">Back to sign in</AuthLink>
        </>
      }
    >
      <form className="space-y-4" onSubmit={onSubmit}>
        {error ? <FormMessage tone="error">{error}</FormMessage> : null}
        {message ? <FormMessage tone="success">{message}</FormMessage> : null}
        <TextField label="Email" type="email" value={email} autoComplete="email" onChange={setEmail} />
        <SubmitButton pending={pending} label="Send reset instructions" />
      </form>
    </AuthCard>
  );
}

import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";

import { AuthCard, AuthLink, FormMessage, SubmitButton, TextField } from "../components/auth/AuthCard.tsx";
import { useAuth } from "../context/AuthContext.tsx";
import { ApiError } from "../services/http.ts";

export function RegisterPage() {
  const { user, loading, register } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  if (loading) {
    return <p className="p-8 text-sm text-slate-600">Checking session…</p>;
  }
  if (user) {
    return <Navigate to="/dashboard" replace />;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    setPending(true);
    try {
      await register({ email, password, full_name: fullName });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Unable to create the account");
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthCard
      title="Create an account"
      footer={
        <>
          Already registered? <AuthLink to="/login">Sign in</AuthLink>
        </>
      }
    >
      <form className="space-y-4" onSubmit={onSubmit}>
        {error ? <FormMessage tone="error">{error}</FormMessage> : null}
        <TextField label="Full name" type="text" value={fullName} autoComplete="name" onChange={setFullName} />
        <TextField label="Email" type="email" value={email} autoComplete="email" onChange={setEmail} />
        <TextField
          label="Password"
          type="password"
          value={password}
          autoComplete="new-password"
          onChange={setPassword}
        />
        <p className="text-xs text-slate-500">Use 10 to 128 characters, including a letter and a number. No email verification is required.</p>
        <TextField
          label="Confirm password"
          type="password"
          value={confirmPassword}
          autoComplete="new-password"
          onChange={setConfirmPassword}
        />
        <SubmitButton pending={pending} label="Create account" />
      </form>
    </AuthCard>
  );
}

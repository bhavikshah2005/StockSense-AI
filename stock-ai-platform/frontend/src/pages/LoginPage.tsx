import { useState, type FormEvent } from "react";
import { Navigate, useSearchParams } from "react-router-dom";

import { AuthCard, AuthLink, FormMessage, SubmitButton, TextField } from "../components/auth/AuthCard.tsx";
import { useAuth } from "../context/AuthContext.tsx";
import { ApiError } from "../services/http.ts";

export function LoginPage() {
  const { user, loading, login } = useAuth();
  const [params] = useSearchParams();
  const justRegistered = params.get("registered") === "1";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
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
    setPending(true);
    try {
      await login(email, password);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Unable to sign in");
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthCard
      title="Sign in"
      footer={
        <>
          <AuthLink to="/forgot-password">Forgot password?</AuthLink>
          <span className="mx-2">·</span>
          Need an account? <AuthLink to="/register">Register</AuthLink>
        </>
      }
    >
      <form className="space-y-4" onSubmit={onSubmit}>
        {justRegistered ? (
          <FormMessage tone="success">Your account is saved. Sign in with the email and password you entered.</FormMessage>
        ) : null}
        {error ? <FormMessage tone="error">{error}</FormMessage> : null}
        <TextField label="Email" type="email" value={email} autoComplete="email" onChange={setEmail} />
        <TextField
          label="Password"
          type="password"
          value={password}
          autoComplete="current-password"
          onChange={setPassword}
        />
        <SubmitButton pending={pending} label="Sign in" />
      </form>
    </AuthCard>
  );
}

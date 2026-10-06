import { useEffect, useState, type FormEvent } from "react";

import { FormMessage, SubmitButton, TextField } from "../components/auth/AuthCard.tsx";
import { useAuth } from "../context/AuthContext.tsx";
import { getNotificationPreferences, updateNotificationPreferences } from "../services/alerts.ts";
import { changePassword, updateProfile } from "../services/auth.ts";
import { ApiError } from "../services/http.ts";

export function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [profileMessage, setProfileMessage] = useState("");
  const [profileError, setProfileError] = useState("");
  const [profilePending, setProfilePending] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordMessage, setPasswordMessage] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [passwordPending, setPasswordPending] = useState(false);

  async function onProfile(event: FormEvent) {
    event.preventDefault();
    setProfileError("");
    setProfileMessage("");
    setProfilePending(true);
    try {
      await updateProfile(fullName);
      await refreshUser();
      setProfileMessage("Profile updated");
    } catch (caught) {
      setProfileError(caught instanceof ApiError ? caught.message : "Unable to update the profile");
    } finally {
      setProfilePending(false);
    }
  }

  async function onPassword(event: FormEvent) {
    event.preventDefault();
    setPasswordError("");
    setPasswordMessage("");
    if (newPassword !== confirmPassword) {
      setPasswordError("Passwords do not match");
      return;
    }
    setPasswordPending(true);
    try {
      await changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordMessage("Password updated");
    } catch (caught) {
      setPasswordError(caught instanceof ApiError ? caught.message : "Unable to change the password");
    } finally {
      setPasswordPending(false);
    }
  }

  return (
    <div className="max-w-xl space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-2 text-sm text-slate-600">{user?.email}</p>
      </header>
      <form className="space-y-4 rounded-lg border border-slate-200 bg-white p-5" onSubmit={onProfile}>
        <h2 className="text-sm font-medium text-slate-500">Profile</h2>
        {profileError ? <FormMessage tone="error">{profileError}</FormMessage> : null}
        {profileMessage ? <FormMessage tone="success">{profileMessage}</FormMessage> : null}
        <TextField label="Full name" type="text" value={fullName} autoComplete="name" onChange={setFullName} />
        <SubmitButton pending={profilePending} label="Save profile" />
      </form>
      <form className="space-y-4 rounded-lg border border-slate-200 bg-white p-5" onSubmit={onPassword}>
        <h2 className="text-sm font-medium text-slate-500">Password</h2>
        {passwordError ? <FormMessage tone="error">{passwordError}</FormMessage> : null}
        {passwordMessage ? <FormMessage tone="success">{passwordMessage}</FormMessage> : null}
        <TextField
          label="Current password"
          type="password"
          value={currentPassword}
          autoComplete="current-password"
          onChange={setCurrentPassword}
        />
        <TextField
          label="New password"
          type="password"
          value={newPassword}
          autoComplete="new-password"
          onChange={setNewPassword}
        />
        <TextField
          label="Confirm new password"
          type="password"
          value={confirmPassword}
          autoComplete="new-password"
          onChange={setConfirmPassword}
        />
        <SubmitButton pending={passwordPending} label="Change password" />
      </form>
      <NotificationSettings />
    </div>
  );
}

export function NotificationSettings() {
  const [enabled, setEnabled] = useState(true);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getNotificationPreferences()
      .then((prefs) => {
        if (!cancelled) {
          setEnabled(prefs.in_app_enabled);
          setLoaded(true);
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof ApiError ? caught.message : "Could not load notification settings");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="space-y-3 rounded-lg border border-slate-200 bg-white p-5" aria-label="Notification settings">
      <h2 className="text-sm font-medium text-slate-500">Notifications</h2>
      {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
      {!loaded && !error ? <p className="text-sm text-slate-600">Loading notification settings…</p> : null}
      <label className="flex items-center gap-2 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => {
            const next = event.target.checked;
            setEnabled(next);
            void updateNotificationPreferences(next).catch((caught: unknown) => {
              setError(caught instanceof ApiError ? caught.message : "Could not save notification settings");
            });
          }}
        />
        In-app notifications
      </label>
      <p className="text-sm text-slate-600">Triggered alerts appear in the app.</p>
    </section>
  );
}

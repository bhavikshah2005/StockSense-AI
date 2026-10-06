import type { AuthUser } from "../types/user.ts";
import { apiRequest } from "./http.ts";

export function fetchCurrentUser(): Promise<AuthUser> {
  return apiRequest<AuthUser>("/api/auth/me");
}

export function login(email: string, password: string): Promise<AuthUser> {
  return apiRequest<AuthUser>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function register(input: {
  email: string;
  password: string;
  full_name: string;
}): Promise<AuthUser> {
  return apiRequest<AuthUser>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function logout(): Promise<void> {
  return apiRequest<void>("/api/auth/logout", { method: "POST" });
}

export function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  return apiRequest<void>("/api/auth/change-password", {
    method: "POST",
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
}

export function forgotPassword(email: string): Promise<{ detail: string }> {
  return apiRequest<{ detail: string }>("/api/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function resetPassword(token: string, newPassword: string): Promise<{ detail: string }> {
  return apiRequest<{ detail: string }>("/api/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, new_password: newPassword }),
  });
}

export function updateProfile(fullName: string): Promise<AuthUser> {
  return apiRequest<AuthUser>("/api/users/me", {
    method: "PATCH",
    body: JSON.stringify({ full_name: fullName }),
  });
}

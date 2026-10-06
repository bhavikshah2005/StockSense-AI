export type AuthUser = {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
};

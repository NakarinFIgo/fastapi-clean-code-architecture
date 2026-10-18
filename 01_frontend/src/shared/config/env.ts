function required(name: keyof ImportMetaEnv): string {
  const value = import.meta.env[name];
  if (!value) throw new Error(`Missing ${name}. Set it in 01_frontend/.env.* (see .env.development).`);
  return value;
}

export const API_BASE_URL = required("VITE_API_BASE_URL");

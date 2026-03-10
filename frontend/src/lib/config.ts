import { z } from "zod";

const envSchema = z.object({
  VITE_API_BASE_URL: z.string().url(),
  VITE_API_KEY: z.string().optional(),
  VITE_DEFAULT_EMPLOYEE_ID: z.string().default("1"),
  VITE_DEFAULT_USER_ROLE: z.string().default("admin"),
});

const parsed = envSchema.safeParse({
  VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL,
  VITE_API_KEY: import.meta.env.VITE_API_KEY,
  VITE_DEFAULT_EMPLOYEE_ID: import.meta.env.VITE_DEFAULT_EMPLOYEE_ID,
  VITE_DEFAULT_USER_ROLE: import.meta.env.VITE_DEFAULT_USER_ROLE,
});

if (!parsed.success) {
  throw new Error(`Invalid frontend env configuration: ${parsed.error.message}`);
}

export const appConfig = {
  apiBaseUrl: parsed.data.VITE_API_BASE_URL,
  defaultApiKey: parsed.data.VITE_API_KEY ?? "",
  defaultEmployeeId: Number(parsed.data.VITE_DEFAULT_EMPLOYEE_ID || "1"),
  defaultUserRole: parsed.data.VITE_DEFAULT_USER_ROLE,
};

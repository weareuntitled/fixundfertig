import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "./api";

const inviteSchema = z.object({
  email: z.string().email(),
  invited_at: z.string().default(""),
});

export type Invite = z.infer<typeof inviteSchema>;

const inviteListSchema = z.array(inviteSchema);

export function useInvites() {
  return useQuery({
    queryKey: ["invites"],
    queryFn: () =>
      api
        .get<unknown>("/api/invites")
        .then((data) => inviteListSchema.parse(data)),
  });
}

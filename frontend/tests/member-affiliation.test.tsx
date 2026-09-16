import { it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemberEditor } from "../src/components/MemberEditor";
import { memberApi } from "../src/services/api";
import type { Profile } from "../src/types/profile";
vi.mock("../src/services/api", () => ({ memberApi: { update: vi.fn() } }));
it("edits chapter, country and region as separate fields", async () => {
  const profile = {
    name: "Member",
    email: "member@example.org",
    supportRaw: "",
    member: { chapter: "Stockholm", country: "Sweden", region: "Europe" },
  } as Profile;
  vi.mocked(memberApi.update).mockResolvedValue(profile);
  const onSave = vi.fn();
  render(<MemberEditor profile={profile} onSave={onSave} />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Edit my information" }));
  expect(screen.getByLabelText("Chapter")).toHaveValue("Stockholm");
  expect(screen.getByLabelText("Country")).toHaveValue("Sweden");
  expect(screen.getByLabelText("Region")).toHaveValue("Europe");
  await user.clear(screen.getByLabelText("Chapter"));
  await user.type(screen.getByLabelText("Chapter"), "Dubai");
  await user.clear(screen.getByLabelText("Country"));
  await user.type(screen.getByLabelText("Country"), "UAE");
  await user.selectOptions(screen.getByLabelText("Region"), "Middle East");
  await user.click(screen.getByRole("button", { name: "Save changes" }));
  expect(memberApi.update).toHaveBeenCalledWith(
    profile.email,
    expect.objectContaining({
      Chapter: "Dubai",
      Country: "UAE",
      Region: "Middle East",
    }),
  );
  expect(onSave).toHaveBeenCalledWith(profile);
});

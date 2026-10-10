import { describe, expect, it } from "vitest";

import { nextSaveName } from "../src/shared/storage";

describe("suggesting the next save name", () => {
  it("adds a number, then counts up", () => {
    expect(nextSaveName("Tower", [])).toBe("Tower 2");
    expect(nextSaveName("Tower 2", [])).toBe("Tower 3");
    expect(nextSaveName("Tower 9", [])).toBe("Tower 10");
  });

  it("skips names that are already taken", () => {
    expect(nextSaveName("Tower", ["Tower", "Tower 2", "Tower 3"])).toBe("Tower 4");
  });

  it("works on a name that is just a number", () => {
    expect(nextSaveName("7", [])).toBe("8");
  });

  it("stays within the length limit", () => {
    const long = "Before the beautiful room";
    expect(nextSaveName(long.slice(0, 24), []).length).toBeLessThanOrEqual(24);
    expect(nextSaveName("x".repeat(24), [])).toBe(`${"x".repeat(22)} 2`);
  });
});

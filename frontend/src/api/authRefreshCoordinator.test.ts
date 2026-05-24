import { describe, expect, it, vi } from "vitest";

import { createAuthRefreshCoordinator } from "./authRefreshCoordinator";

describe("createAuthRefreshCoordinator", () => {
  it("shares one refresh request between concurrent callers", async () => {
    const refreshAccessToken = vi.fn(async () => "new-access-token");
    const coordinator = createAuthRefreshCoordinator({ refreshAccessToken });

    const [first, second, third] = await Promise.all([
      coordinator.refresh(),
      coordinator.refresh(),
      coordinator.refresh(),
    ]);

    expect(first).toBe("new-access-token");
    expect(second).toBe("new-access-token");
    expect(third).toBe("new-access-token");
    expect(refreshAccessToken).toHaveBeenCalledTimes(1);
  });

  it("allows a new refresh after the previous one settles", async () => {
    const refreshAccessToken = vi.fn(async () => "new-access-token");
    const coordinator = createAuthRefreshCoordinator({ refreshAccessToken });

    await coordinator.refresh();
    await coordinator.refresh();

    expect(refreshAccessToken).toHaveBeenCalledTimes(2);
  });

  it("notifies refresh failures and resets the in-flight state", async () => {
    const error = new Error("refresh failed");
    const onRefreshFailure = vi.fn();
    const refreshAccessToken = vi
      .fn()
      .mockRejectedValueOnce(error)
      .mockResolvedValueOnce("recovered-token");
    const coordinator = createAuthRefreshCoordinator({ refreshAccessToken, onRefreshFailure });

    await expect(coordinator.refresh()).rejects.toThrow("refresh failed");
    await expect(coordinator.refresh()).resolves.toBe("recovered-token");

    expect(onRefreshFailure).toHaveBeenCalledWith(error);
    expect(refreshAccessToken).toHaveBeenCalledTimes(2);
  });
});

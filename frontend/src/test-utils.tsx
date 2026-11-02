import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});

export { render, screen, waitFor, act, within } from "@testing-library/react";
export { default as userEvent } from "@testing-library/user-event";

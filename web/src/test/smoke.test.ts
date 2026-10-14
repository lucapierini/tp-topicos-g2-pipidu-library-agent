import { expect, test } from "vitest"

test("el entorno de pruebas arranca", () => {
  expect(document).toBeDefined()
})

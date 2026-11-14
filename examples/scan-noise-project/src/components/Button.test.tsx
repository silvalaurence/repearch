import { render } from "@testing-library/react-native";
import { Button } from "./Button";

test("Button renders", () => {
  expect(render(<Button label="Book" />)).toBeTruthy();
});

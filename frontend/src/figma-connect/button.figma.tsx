/**
 * Figma Code Connect — Button
 *
 * TODO: Replace the placeholder URL below with the real Figma component URL.
 * How to get it:
 *   1. Open your Figma design file.
 *   2. Right-click the Button component in the Assets panel (or on canvas).
 *   3. Choose "Copy link to component".
 *   4. Paste it here, e.g.:
 *      https://www.figma.com/design/FILEKEYHERE/Coloring-Book-Studio?node-id=123-456
 *
 * After updating the URL, run:
 *   pnpm figma:connect
 * (requires FIGMA_ACCESS_TOKEN env var — generate one at figma.com/settings → Personal access tokens)
 */

import figma from "@figma/code-connect"
import { Button } from "@/components/ui/button"

// TODO: replace URL — needs real Figma file key + Button component node-id
const FIGMA_BUTTON_URL =
  "https://www.figma.com/design/TODO_FILE_KEY/Coloring-Book-Studio?node-id=TODO-BUTTON"

figma.connect(Button, FIGMA_BUTTON_URL, {
  props: {
    /**
     * Map the Figma "Variant" property to the React variant prop.
     * Adjust the Figma property name ("Variant") to match what your file uses.
     */
    variant: figma.enum("Variant", {
      Default:     "default",
      Outline:     "outline",
      Secondary:   "secondary",
      Ghost:       "ghost",
      Destructive: "destructive",
      Link:        "link",
    }),

    /**
     * Map the Figma "Size" property to the React size prop.
     */
    size: figma.enum("Size", {
      Default: "default",
      XS:      "xs",
      SM:      "sm",
      LG:      "lg",
      Icon:    "icon",
    }),

    /** The button label text node. Adjust "Label" to match your Figma layer name. */
    children: figma.string("Label"),
  },

  example({ variant, size, children }) {
    return (
      <Button variant={variant} size={size}>
        {children}
      </Button>
    )
  },
})

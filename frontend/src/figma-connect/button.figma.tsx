import figma from "@figma/code-connect"
import { Button } from "@/components/ui/button"

// Figma component: Button ComponentSet — file mC044MH1WirZ5Hzh2PILML, node 4:7
// Variants: Variant=Primary (amber, default) | Variant=Secondary (outline)
const FIGMA_BUTTON_URL =
  "https://www.figma.com/design/mC044MH1WirZ5Hzh2PILML/Coloring-Book-Studio--Design-System?node-id=4-7"

figma.connect(Button, FIGMA_BUTTON_URL, {
  props: {
    variant: figma.enum("Variant", {
      Primary:   "default",
      Secondary: "outline",
    }),
    children: figma.string("Label"),
  },

  example({ variant, children }) {
    return (
      <Button variant={variant}>
        {children}
      </Button>
    )
  },
})

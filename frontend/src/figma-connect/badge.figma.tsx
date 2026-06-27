import figma from "@figma/code-connect"
import { Badge } from "@/components/ui/badge"

// Figma component: Badge ComponentSet — file mC044MH1WirZ5Hzh2PILML, node 4:24
// 8 status variants matching the coloring-book page workflow
const FIGMA_BADGE_URL =
  "https://www.figma.com/design/mC044MH1WirZ5Hzh2PILML/Coloring-Book-Studio--Design-System?node-id=4-24"

figma.connect(Badge, FIGMA_BADGE_URL, {
  props: {
    variant: figma.enum("Status", {
      "Idea":        "idea",
      "Prompt":      "prompt",
      "Generated":   "generated",
      "Review":      "review",
      "Revision":    "revision",
      "Approved":    "approved",
      "Print Ready": "print_ready",
      "Exported":    "exported",
    }),
  },

  example({ variant }) {
    return <Badge variant={variant} />
  },
})

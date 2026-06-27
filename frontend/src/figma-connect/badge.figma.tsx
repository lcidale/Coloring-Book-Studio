/**
 * Figma Code Connect — Badge
 *
 * This Badge maps to the coloring-book page workflow statuses as well as
 * semantic color aliases. Each Figma variant value maps to its React prop.
 *
 * TODO: Replace the placeholder URL below with the real Figma component URL.
 * How to get it:
 *   1. Open your Figma design file.
 *   2. Right-click the Badge / Status Chip component in the Assets panel.
 *   3. Choose "Copy link to component".
 *   4. Paste it here, e.g.:
 *      https://www.figma.com/design/FILEKEYHERE/Coloring-Book-Studio?node-id=125-321
 *
 * After updating the URL, run:
 *   pnpm figma:connect
 */

import figma from "@figma/code-connect"
import { Badge } from "@/components/ui/badge"

// TODO: replace URL — needs real Figma file key + Badge component node-id
const FIGMA_BADGE_URL =
  "https://www.figma.com/design/TODO_FILE_KEY/Coloring-Book-Studio?node-id=TODO-BADGE"

figma.connect(Badge, FIGMA_BADGE_URL, {
  props: {
    /**
     * Map the Figma "Variant" (or "Status") property to the React variant prop.
     * Include all page-workflow statuses your Figma file defines.
     * Adjust Figma-side names to match your actual component property values.
     */
    variant: figma.enum("Variant", {
      // Semantic colour aliases
      Green:  "green",
      Blue:   "blue",
      Yellow: "yellow",
      Red:    "red",
      Purple: "purple",
      Gray:   "gray",

      // Page workflow statuses
      Idea:        "idea",
      Prompt:      "prompt",
      Generated:   "generated",
      Review:      "review",
      Revision:    "revision",
      Approved:    "approved",
      "Print Ready": "print_ready",
      Exported:    "exported",

      // shadcn-compat variants
      Default:     "default",
      Outline:     "outline",
      Secondary:   "secondary",
      Destructive: "destructive",
    }),

    /**
     * Whether the badge shows a colour dot prefix.
     * Adjust "Show Dot" to the actual boolean property name in your file.
     */
    dot: figma.boolean("Show Dot"),

    /** The badge label text. Adjust "Label" to match your Figma layer name. */
    children: figma.string("Label"),
  },

  example({ variant, dot, children }) {
    return (
      <Badge variant={variant} dot={dot}>
        {children}
      </Badge>
    )
  },
})

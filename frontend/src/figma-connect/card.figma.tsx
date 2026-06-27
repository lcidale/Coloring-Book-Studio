/**
 * Figma Code Connect — Card
 *
 * TODO: Replace the placeholder URL below with the real Figma component URL.
 * How to get it:
 *   1. Open your Figma design file.
 *   2. Right-click the Card component in the Assets panel.
 *   3. Choose "Copy link to component".
 *   4. Paste it here, e.g.:
 *      https://www.figma.com/design/FILEKEYHERE/Coloring-Book-Studio?node-id=124-789
 *
 * After updating the URL, run:
 *   pnpm figma:connect
 */

import figma from "@figma/code-connect"
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardAction,
  CardFooter,
} from "@/components/ui/card"

// TODO: replace URL — needs real Figma file key + Card component node-id
const FIGMA_CARD_URL =
  "https://www.figma.com/design/TODO_FILE_KEY/Coloring-Book-Studio?node-id=TODO-CARD"

figma.connect(Card, FIGMA_CARD_URL, {
  props: {
    /**
     * Map the Figma "Size" property. Adjust name if your file differs.
     */
    size: figma.enum("Size", {
      Default: "default",
      SM:      "sm",
    }),

    /** Title text — adjust "Title" to match your Figma layer name. */
    title: figma.string("Title"),

    /** Description text — adjust "Description" to match. */
    description: figma.string("Description"),

    /** Whether the card has a visible footer. */
    hasFooter: figma.boolean("Has Footer"),
  },

  example({ size, title, description, hasFooter }) {
    return (
      <Card size={size}>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </CardHeader>
        <CardContent>
          {/* card body content */}
        </CardContent>
        {hasFooter && (
          <CardFooter>
            {/* footer content */}
          </CardFooter>
        )}
      </Card>
    )
  },
})

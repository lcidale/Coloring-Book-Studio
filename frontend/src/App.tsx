import { Toaster } from "@/components/ui/sonner"
import { GalleryPage } from "@/features/gallery/GalleryPage"

/**
 * App — root component.
 * During U3 development the app renders the component gallery.
 * Later phases will add a router and real views.
 */
function App() {
  return (
    <>
      <GalleryPage />
      <Toaster position="bottom-right" richColors />
    </>
  )
}

export default App

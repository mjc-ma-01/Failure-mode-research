"""Place the generated scientific figure on a 4:3 slide without distorting it."""

from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches


ROOT = Path(__file__).resolve().parent
figure = ROOT / "figure1_academic.png"
with Image.open(figure) as image:
    image_width, image_height = image.size

deck = Presentation()
deck.slide_width = Inches(12)
deck.slide_height = Inches(9)
deck.core_properties.title = "Learning Agent Safety: Model-Harness Co-evolution"
deck.core_properties.subject = "Research Figure 1; generated raster artwork"
slide = deck.slides.add_slide(deck.slide_layouts[6])
slide.background.fill.solid()
slide.background.fill.fore_color.rgb = RGBColor(255, 255, 255)
scale = min(12 / image_width, 9 / image_height)
width, height = image_width * scale, image_height * scale
slide.shapes.add_picture(
    str(figure),
    Inches((12 - width) / 2),
    Inches((9 - height) / 2),
    width=Inches(width),
    height=Inches(height),
)
slide.notes_slide.notes_text_frame.text = (
    "This slide contains the generated English Figure 1 as one raster image. "
    "Its text and modules are not separate editable PowerPoint elements. "
    "The source prompt and figure caption are included alongside this file. "
    "The figure describes a proposed mechanism, not measured results."
)
deck.save(ROOT / "figure1_academic_image_slide.pptx")
print(f"Packaged {image_width} x {image_height} image on a 4:3 slide")

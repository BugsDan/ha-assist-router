"""Original speech-bubble / three-route mark; deterministic SVG and RGBA PNGs."""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
PALETTES = {"icon": ("#123047", "#F7FAFC", "#31D4B8"), "dark_icon": ("#E6EFFB", "#123047", "#087D79")}


def svg(background, line, node):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  <title>Assist Router</title>
  <desc>Original speech bubble connecting one input to three ordered destinations.</desc>
  <path fill="{background}" d="M48 0H208Q256 0 256 48V176Q256 224 208 224H96L48 256V224Q0 224 0 176V48Q0 0 48 0Z"/>
  <path fill="none" stroke="{line}" stroke-width="12" stroke-linecap="round" stroke-linejoin="round" d="M64 112H192M144 56V168M144 56H192M144 168H192"/>
  <g fill="{node}"><circle cx="64" cy="112" r="24"/><circle cx="192" cy="56" r="16"/><circle cx="192" cy="112" r="16"/><circle cx="192" cy="168" r="16"/></g>
</svg>
'''


def render(size, palette):
    background, line, node = palette
    scale = 8
    image = Image.new("RGBA", (256 * scale, 256 * scale))
    draw = ImageDraw.Draw(image)

    def points(values):
        return [(x * scale, y * scale) for x, y in values]

    draw.rounded_rectangle((0, 0, 256 * scale - 1, 224 * scale - 1), radius=48 * scale, fill=background)
    draw.polygon(points([(48, 220), (48, 255.875), (96, 220)]), fill=background)
    for segment in (
        [(64, 112), (192, 112)],
        [(144, 56), (144, 168)],
        [(144, 56), (192, 56)],
        [(144, 168), (192, 168)],
    ):
        draw.line(points(segment), fill=line, width=12 * scale)
        for x, y in segment:
            draw.ellipse(((x - 6) * scale, (y - 6) * scale, (x + 6) * scale, (y + 6) * scale), fill=line)
    for x, y, radius in ((64, 112, 24), (192, 56, 16), (192, 112, 16), (192, 168, 16)):
        draw.ellipse(
            ((x - radius) * scale, (y - radius) * scale, (x + radius) * scale, (y + radius) * scale),
            fill=node,
        )
    return image.resize((size, size), Image.Resampling.LANCZOS)


def main():
    assets = ROOT / "assets"
    brand = ROOT / "custom_components/assist_router/brand"
    assets.mkdir(exist_ok=True)
    brand.mkdir(exist_ok=True)
    for name, palette in PALETTES.items():
        (assets / f"{name}.svg").write_text(svg(*palette), encoding="utf-8")
        for size, suffix in ((256, ""), (512, "@2x")):
            render(size, palette).save(brand / f"{name}{suffix}.png", optimize=True)
    print("Generated original SVGs and local 256/512px PNG brand assets.")


if __name__ == "__main__":
    main()

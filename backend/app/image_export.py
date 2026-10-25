"""Presentation-size PNG exports. Interpolation never adds sensor information."""
from io import BytesIO

from PIL import Image, ImageChops

HIGHLIGHT_BLUE = (5, 148, 242)


def presentation_png(blob: bytes, scale: int, natural_blob: bytes | None = None) -> bytes:
    if scale == 1:
        return blob
    if scale not in (2, 4):
        raise ValueError('Ampliação deve ser 1×, 2× ou 4×')
    with Image.open(BytesIO(blob)) as source:
        source.load()
        if source.width * source.height > 2_000_000:
            raise ValueError('Imagem original grande demais para ampliar')
        target_size = (source.width * scale, source.height * scale)
        if natural_blob is None:
            enlarged = source.resize(target_size, Image.Resampling.LANCZOS)
        else:
            with Image.open(BytesIO(natural_blob)) as natural:
                natural.load()
                if natural.size != source.size:
                    raise ValueError('Cor natural e destaque de água têm dimensões diferentes')
                # Interpolate only the visual background. Classified water is a
                # categorical observation, so its footprint must stay unchanged.
                selected = ImageChops.difference(source.convert('RGB'),
                    Image.new('RGB', source.size, HIGHLIGHT_BLUE))
                red, green, blue = selected.split()
                mask = ImageChops.lighter(ImageChops.lighter(red, green), blue).point(
                    lambda value: 255 if value == 0 else 0)
                changed = ImageChops.difference(source.convert('RGB'), natural.convert('RGB'))
                red, green, blue = changed.split()
                changed_mask = ImageChops.lighter(ImageChops.lighter(red, green), blue).point(
                    lambda value: 255 if value else 0)
                mask = ImageChops.darker(mask, changed_mask)
                mask = ImageChops.darker(mask, source.convert('RGBA').getchannel('A'))
                enlarged = Image.composite(
                    Image.new('RGBA', target_size, (*HIGHLIGHT_BLUE, 255)),
                    natural.convert('RGBA').resize(target_size, Image.Resampling.LANCZOS),
                    mask.resize(target_size, Image.Resampling.NEAREST))
        output = BytesIO()
        enlarged.save(output, format='PNG')
        return output.getvalue()

"""Presentation-size PNG exports. Interpolation never adds sensor information."""
from io import BytesIO

from PIL import Image


def presentation_png(blob: bytes, scale: int) -> bytes:
    if scale == 1:
        return blob
    if scale not in (2, 4):
        raise ValueError('Ampliação deve ser 1×, 2× ou 4×')
    with Image.open(BytesIO(blob)) as source:
        source.load()
        if source.width * source.height > 2_000_000:
            raise ValueError('Imagem original grande demais para ampliar')
        enlarged = source.resize((source.width * scale, source.height * scale), Image.Resampling.LANCZOS)
        output = BytesIO()
        enlarged.save(output, format='PNG')
        return output.getvalue()

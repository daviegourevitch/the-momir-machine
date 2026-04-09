Step-by-step pipeline — facts about each stage
1. Flatten alpha / transparency
PNG images may have an alpha channel. Before converting, you must flatten layers onto a white background by removing the alpha channel and merging with a white background. Screaming In ImageMagick:
bash-background white -alpha remove -alpha off
In PIL:
pythonimg = img.convert("RGBA")
background = Image.new("RGBA", img.size, (255, 255, 255, 255))
background.paste(img, mask=img.split()[3])
img = background.convert("RGB")

2. Convert to grayscale
This must be done before thresholding or dithering. In ImageMagick:
bash-colorspace Gray
In PIL:
pythonimg = img.convert("L")
PIL uses the ITU-R 601-2 luma transform when converting a color image to grayscale ("L" mode). Pillow Documentation

3. Gamma correction
Thermal printers tend to print darker than a digital preview, so applying a gamma correction before dithering compensates for this. A gamma value of 1.8 is used specifically for this correction in thermal printer workflows. Screaming
In ImageMagick:
bash-gamma 1.8
In PIL:
pythonimport numpy as np
arr = np.array(img, dtype=np.float32) / 255.0
arr = np.power(arr, 1.0 / 1.8)
img = Image.fromarray((arr * 255).astype(np.uint8))

4. Contrast stretching
-contrast-stretch increases contrast in an image by stretching the range of intensity values. With 0 as the argument, it stretches the image's min and max values to 0 and QuantumRange respectively without any clipping. ImageMagick
bash-contrast-stretch 2%x1%
PIL equivalent uses ImageEnhance:
pythonfrom PIL import ImageEnhance
img = ImageEnhance.Contrast(img).enhance(2.0)

5. Unsharp mask (before dithering)
Applying unsharp mask before the dithering step increases local contrast at edges, which directly affects how crisply text separates from its background in the final 1-bit result.
-unsharp takes the difference between the original and a blurred version of the image (an edge result), then blends some fraction of that back with the original, but only if the difference exceeds a threshold. The parameters are radiusxsigma+amount+threshold. ImageMagick
bash-unsharp 0x1+1.5+0.02
Any sharpening process increases local contrast. At an edge — such as the edge of light lettering against a dark background — light pixels become lighter and dark pixels become darker. With a suitable sigma, the effect carries across the width of each letter stroke. ImageMagick
In PIL:
pythonfrom PIL import ImageFilter
img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))

6. Dithering / thresholding — the core decision
There are three distinct approaches:
A. Floyd-Steinberg error diffusion
Floyd-Steinberg dithering distributes quantization error to neighboring pixels in a specific weighted pattern: 7/16 to the right, 3/16 to the lower-left, 5/16 directly below, and 1/16 to the lower-right. The algorithm scans top-to-bottom, left-to-right. SciPython
The dither:diffusion-amount define controls the percentage of Floyd-Steinberg diffusion. It can be set like -define dither:diffusion-amount=85%. ImageMagick
In ImageMagick:
bash-dither FloydSteinberg -define dither:diffusion-amount=85% -monochrome
Lower diffusion-amount values tend to cause light areas to "blow out," while higher values produce a "snowy" appearance. The ideal setting varies image to image. Adafruit
PIL's default method when converting from "L" or "RGB" to mode "1" uses Floyd-Steinberg dithering. Pillow Documentation
pythonimg_1bit = img.convert("1")  # Floyd-Steinberg by default
B. Hard threshold (no dithering)
When dither=NONE is used in PIL's conversion to mode "1", all values greater than 127 are set to white (255), all others to black (0). GitHub
pythonimg_1bit = img.convert("1", dither=Image.NONE)
In ImageMagick:
bash+dither -threshold 50%
Disabling dithering may be useful for text, high-contrast line art; it results in more cartoon-like image coloring with color banding in areas with gradients. Adafruit
C. Ordered (Bayer) dithering
Ordered dithering uses a structured pattern. It tends to lose edge details but may provide a "clean" look for flat artwork and diagrams. The o8x8, o4x4, and o2x2 matrix sizes give different results. Adafruit
bash-ordered-dither o8x8

7. Forcing 1-bit output
To force a true 1-bit bilevel image in ImageMagick, use -colors 2 +dither -type bilevel. ImageMagick
Using -type Bilevel produces a 1-bit output but is significantly slower than -threshold 50% or -ordered-dither approaches. Narkive
For a true 1-bit BMP specifically, the sequence convert to PNG (8-bit gray, 2 colors) then convert PNG to BMP results in a 1-bit BMP file. GitHub

Complete example pipelines
ImageMagick — Floyd-Steinberg with pre-processing:
bashmagick input.png \
  -background white -alpha remove -alpha off \
  -colorspace Gray \
  -gamma 1.8 \
  -contrast-stretch 2%x1% \
  -unsharp 0x1+1.5+0.02 \
  -dither FloydSteinberg -define dither:diffusion-amount=85% \
  -type bilevel \
  output.bmp
ImageMagick — Hard threshold (cleaner text, less artwork detail):
bashmagick input.png \
  -background white -alpha remove -alpha off \
  -colorspace Gray \
  -gamma 1.8 \
  -contrast-stretch 2%x1% \
  -unsharp 0x1+2.0+0.02 \
  +dither -threshold 55% \
  -type bilevel \
  output.bmp
PIL — Floyd-Steinberg with pre-processing:
pythonfrom PIL import Image, ImageEnhance, ImageFilter
import numpy as np

img = Image.open("input.png").convert("RGBA")
bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
bg.paste(img, mask=img.split()[3])
img = bg.convert("RGB").convert("L")

# Gamma correction for thermal printer
arr = np.array(img, dtype=np.float32) / 255.0
arr = np.power(arr, 1.0 / 1.8)
img = Image.fromarray((arr * 255).astype(np.uint8))

img = ImageEnhance.Contrast(img).enhance(2.0)
img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))

img_1bit = img.convert("1")  # Floyd-Steinberg
img_1bit.save("output.bmp")

Tradeoffs table specific to MtG card content
ParameterEffect on card textEffect on card artFloyd-Steinberg at 85%Noise can intrude on text box bordersGood midtone reproduction in artworkFloyd-Steinberg at 50–60%Somewhat cleaner text boundariesMore contrast loss in artworkHard threshold at 50%Cleanest text strokesHeavy posterization in artworkHard threshold at 55–60%Tends to fill in thin strokesMore dark areas lost in artworkUnsharp mask before ditherIncreases edge contrast, improves text separationCan cause halo artifacts in artworkGamma 1.8Prevents text boxes from printing too darkPrevents overall print muddiness-contrast-stretch 2%x1%Expands tonal range across the full cardSame

The structure-aware-dithering Python library was written specifically with thermal printing as its primary use case and implements multiple algorithms beyond Floyd-Steinberg including contrast-aware halftoning, entropy-constrained threshold modulation, and the Zhang-Pang algorithm — all of which are documented to improve edge and texture preservation over standard Floyd-Steinberg. GitHub It is available at https://github.com/dalpil/structure-aware-dithering.
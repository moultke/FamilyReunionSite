import pyheif
from PIL import Image


def convert_heic_to_jpg(heic_path, output_path):
    heif_file = pyheif.read(heic_path)
    image = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, "raw", heif_file.mode)
    image.save(output_path, "JPEG")
    print(f"✅ Converted {heic_path} to {output_path}")

# Test with an actual HEIC file
convert_heic_to_jpg("input.heic", "output.jpg")
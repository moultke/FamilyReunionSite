import pyheif

print(pyheif.__version__)  # Print the version

try:
    raise pyheif.HeifError("Test")  # Try raising the exception
except pyheif.HeifError as e:
    print("HeifError caught:", e)
except Exception as e:
    print("Some other exception caught:", e)

print("Import and test successful")
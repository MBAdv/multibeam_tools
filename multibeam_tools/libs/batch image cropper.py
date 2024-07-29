import glob
import os
from tkinter import filedialog as fd

from PIL import Image

directory_path = fd.askdirectory()

Images = glob.glob(os.path.join(directory_path,"*.jpg"))

for image_file_and_path in Images:
    image_filename = os.path.basename(image_file_and_path)
    output_filename = os.path.join(r'C:\Users\kjerram\Desktop\MAC UNOLS\ARMSTRONG\2024 EM124 EM712 SAT\Screendumps\EM124\cropped', image_filename)
    uncropped_image = Image.open(image_file_and_path)

    # The argument to crop is a box : a 4-tuple defining the left, upper, right, and lower pixel positions.
    left = 60
    top = 21
    width = 1076
    height = 629

    CroppedImg = uncropped_image.crop((left, top, width + left, height + top))

    CroppedImg.save(output_filename)
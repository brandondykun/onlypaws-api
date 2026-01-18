import io
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, ImageOps
from io import BytesIO

from apps.core_app.utils import crop_to_aspect_ratio_and_resize


class CropToAspectRatioAndResizeTestCase(TestCase):
    """Test suite for crop_to_aspect_ratio_and_resize utility function"""

    def create_test_image(self, width, height, color='red', format='JPEG', filename='test.jpg', exif_rotation=None):
        """Helper method to create test images with optional EXIF rotation"""
        img = Image.new('RGB', (width, height), color=color)
        
        # Add EXIF rotation data if specified
        if exif_rotation:
            from PIL.Image import Exif
            exif = Exif()
            exif[0x0112] = exif_rotation  # Orientation tag
            img_bytes = BytesIO()
            img.save(img_bytes, format=format, exif=exif)
        else:
            img_bytes = BytesIO()
            img.save(img_bytes, format=format)
        
        img_bytes.seek(0)
        return SimpleUploadedFile(filename, img_bytes.read(), content_type=f'image/{format.lower()}')

    def test_square_image_to_1_1_no_crop(self):
        """Test that a square image for 1:1 aspect ratio requires no cropping"""
        image = self.create_test_image(1080, 1080)
        result = crop_to_aspect_ratio_and_resize(image, aspect_ratio="1:1")
        
        # Verify the result
        result.seek(0)
        result_img = Image.open(result)
        self.assertEqual(result_img.size, (1080, 1080))
        self.assertEqual(result.name, 'test.webp')

    def test_landscape_image_to_1_1_crops_sides(self):
        """Test that a landscape image is cropped on left and right for 1:1"""
        image = self.create_test_image(2000, 1000)
        result = crop_to_aspect_ratio_and_resize(image, aspect_ratio="1:1")
        
        result.seek(0)
        result_img = Image.open(result)
        # Should be cropped to 1000x1000, then not resized (since < 1080)
        self.assertEqual(result_img.size, (1000, 1000))

    def test_portrait_image_to_1_1_crops_top_bottom(self):
        """Test that a portrait image is cropped on top and bottom for 1:1"""
        image = self.create_test_image(1000, 2000)
        result = crop_to_aspect_ratio_and_resize(image, aspect_ratio="1:1")
        
        result.seek(0)
        result_img = Image.open(result)
        # Should be cropped to 1000x1000
        self.assertEqual(result_img.size, (1000, 1000))

    def test_4_5_aspect_ratio(self):
        """Test 4:5 aspect ratio conversion"""
        image = self.create_test_image(2000, 2000)
        result = crop_to_aspect_ratio_and_resize(image, aspect_ratio="4:5")
        
        result.seek(0)
        result_img = Image.open(result)
        # Should be 1080x1350 (from ASPECT_RATIO_DIMENSIONS)
        self.assertEqual(result_img.size, (1080, 1350))

    def test_large_image_is_resized(self):
        """Test that images larger than target are resized down"""
        image = self.create_test_image(3000, 3000)
        result = crop_to_aspect_ratio_and_resize(image, aspect_ratio="1:1", base_width=1080)
        
        result.seek(0)
        result_img = Image.open(result)
        self.assertEqual(result_img.size, (1080, 1080))

    def test_small_image_not_upscaled(self):
        """Test that images smaller than target are NOT upscaled"""
        image = self.create_test_image(500, 500)
        result = crop_to_aspect_ratio_and_resize(image, aspect_ratio="1:1", base_width=1080)
        
        result.seek(0)
        result_img = Image.open(result)
        # Should remain 500x500, not upscaled to 1080x1080
        self.assertEqual(result_img.size, (500, 500))

    def test_custom_base_width(self):
        """Test custom base_width parameter"""
        image = self.create_test_image(2000, 2000)
        result = crop_to_aspect_ratio_and_resize(image, aspect_ratio="1:1", base_width=500)
        
        result.seek(0)
        result_img = Image.open(result)
        self.assertEqual(result_img.size, (500, 500))

    def test_custom_base_width_with_4_5_ratio(self):
        """Test custom base_width with 4:5 ratio (should calculate height)"""
        image = self.create_test_image(2000, 2500)
        result = crop_to_aspect_ratio_and_resize(image, aspect_ratio="4:5", base_width=800)
        
        result.seek(0)
        result_img = Image.open(result)
        # 800 width, height should be 800 / (4/5) = 1000
        self.assertEqual(result_img.size, (800, 1000))

    def test_output_is_webp_format(self):
        """Test that output is always in webp format"""
        image = self.create_test_image(1080, 1080)
        result = crop_to_aspect_ratio_and_resize(image, aspect_ratio="1:1")
        
        result.seek(0)
        result_img = Image.open(result)
        self.assertEqual(result_img.format, 'WEBP')

    def test_filename_conversion_to_webp(self):
        """Test that filename is converted to .webp extension"""
        image = self.create_test_image(1080, 1080, filename='my_image.png')
        result = crop_to_aspect_ratio_and_resize(image, aspect_ratio="1:1")
        
        self.assertEqual(result.name, 'my_image.webp')

    def test_filename_with_multiple_dots(self):
        """Test filename handling with multiple dots"""
        image = self.create_test_image(1080, 1080, filename='my.image.file.jpg')
        result = crop_to_aspect_ratio_and_resize(image, aspect_ratio="1:1")
        
        # Should only replace the last extension
        self.assertEqual(result.name, 'my.webp')

    def test_exif_orientation_handled(self):
        """Test that EXIF orientation data is properly handled"""
        # Create image with EXIF rotation (orientation = 6 means rotate 90° CW)
        image = self.create_test_image(1080, 1350, exif_rotation=6)
        
        with patch.object(ImageOps, 'exif_transpose') as mock_exif:
            mock_exif.return_value = Image.new('RGB', (1350, 1080), color='red')
            result = crop_to_aspect_ratio_and_resize(image, aspect_ratio="1:1")
            
            # Verify exif_transpose was called
            mock_exif.assert_called_once()

    def test_aspect_ratio_already_matches(self):
        """Test when image already matches target aspect ratio within tolerance"""
        # Create image with 4:5 ratio (1080x1350)
        image = self.create_test_image(1080, 1350)
        result = crop_to_aspect_ratio_and_resize(image, aspect_ratio="4:5")
        
        result.seek(0)
        result_img = Image.open(result)
        # Should not be cropped, dimensions should remain
        self.assertEqual(result_img.size, (1080, 1350))

    def test_aspect_ratio_tolerance(self):
        """Test aspect ratio tolerance of 0.001"""
        # Create image with ratio very close to 1:1 (within tolerance)
        image = self.create_test_image(1080, 1081)  # Ratio: 0.9990...
        result = crop_to_aspect_ratio_and_resize(image, aspect_ratio="1:1")
        
        result.seek(0)
        result_img = Image.open(result)
        # Should be treated as already matching, no crop
        self.assertEqual(result_img.size, (1080, 1081))

    def test_very_wide_image(self):
        """Test extremely wide image (panorama)"""
        image = self.create_test_image(5000, 1000)
        result = crop_to_aspect_ratio_and_resize(image, aspect_ratio="1:1")
        
        result.seek(0)
        result_img = Image.open(result)
        # Should be cropped to 1000x1000 (center crop)
        self.assertEqual(result_img.size, (1000, 1000))

    def test_very_tall_image(self):
        """Test extremely tall image"""
        image = self.create_test_image(1000, 5000)
        result = crop_to_aspect_ratio_and_resize(image, aspect_ratio="1:1")
        
        result.seek(0)
        result_img = Image.open(result)
        # Should be cropped to 1000x1000 (center crop)
        self.assertEqual(result_img.size, (1000, 1000))

    def test_png_input(self):
        """Test that PNG input is handled correctly"""
        image = self.create_test_image(1080, 1080, format='PNG', filename='test.png')
        result = crop_to_aspect_ratio_and_resize(image, aspect_ratio="1:1")
        
        self.assertEqual(result.name, 'test.webp')
        result.seek(0)
        result_img = Image.open(result)
        self.assertEqual(result_img.format, 'WEBP')

    def test_center_crop_accuracy(self):
        """Test that cropping is properly centered"""
        # Create a 3000x1000 image to be cropped to 1:1
        image = self.create_test_image(3000, 1000)
        
        # Capture crop arguments while still calling the real method
        original_crop = Image.Image.crop
        crop_args = []
        
        def capture_crop(self, box):
            crop_args.append(box)
            return original_crop(self, box)
        
        with patch.object(Image.Image, 'crop', capture_crop):
            result = crop_to_aspect_ratio_and_resize(image, aspect_ratio="1:1")
            
            # Should crop to 1000x1000 centered horizontally
            # left = (3000 - 1000) / 2 = 1000
            # Crop box should be (1000, 0, 2000, 1000)
            self.assertEqual(len(crop_args), 1)
            crop_box = crop_args[0]
            self.assertEqual(crop_box, (1000.0, 0, 2000.0, 1000))

    def test_invalid_aspect_ratio_format(self):
        """Test handling of invalid aspect ratio format"""
        image = self.create_test_image(1080, 1080)
        
        with self.assertRaises(ValueError):
            crop_to_aspect_ratio_and_resize(image, aspect_ratio="invalid")

    def test_aspect_ratio_dimensions_lookup(self):
        """Test that ASPECT_RATIO_DIMENSIONS is used correctly for default base_width"""
        image = self.create_test_image(2000, 2000)
        
        # For 1:1 with base_width=1080, should use (1080, 1080) from dict
        result_1_1 = crop_to_aspect_ratio_and_resize(image, aspect_ratio="1:1", base_width=1080)
        result_1_1.seek(0)
        img_1_1 = Image.open(result_1_1)
        self.assertEqual(img_1_1.size, (1080, 1080))
        
        # For 4:5 with base_width=1080, should use (1080, 1350) from dict
        result_4_5 = crop_to_aspect_ratio_and_resize(image, aspect_ratio="4:5", base_width=1080)
        result_4_5.seek(0)
        img_4_5 = Image.open(result_4_5)
        self.assertEqual(img_4_5.size, (1080, 1350))
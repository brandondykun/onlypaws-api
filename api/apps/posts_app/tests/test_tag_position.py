from django.test import TestCase
from apps.posts_app.views import adjust_tag_position_for_center_crop


class AdjustTagPositionForCenterCropTestCase(TestCase):
    """Test suite for adjust_tag_position_for_center_crop utility function"""

    # ==================== No Crop Needed Tests ====================
    
    def test_square_image_to_1_1_no_adjustment(self):
        """Test that square image (1:1) to 1:1 requires no adjustment"""
        x, y = adjust_tag_position_for_center_crop(
            x_percent=50, y_percent=50,
            original_width=1000, original_height=1000,
            target_aspect_ratio="1:1"
        )
        self.assertEqual(x, 50)
        self.assertEqual(y, 50)

    def test_4_5_image_to_4_5_no_adjustment(self):
        """Test that 4:5 image to 4:5 requires no adjustment"""
        x, y = adjust_tag_position_for_center_crop(
            x_percent=25, y_percent=75,
            original_width=1000, original_height=1250,
            target_aspect_ratio="4:5"
        )
        self.assertEqual(x, 25)
        self.assertEqual(y, 75)

    def test_ratio_within_tolerance(self):
        """Test that ratios within 0.001 tolerance are treated as matching"""
        # 1000/1001 = 0.999000999... which is within 0.001 of 1.0
        x, y = adjust_tag_position_for_center_crop(
            x_percent=30, y_percent=70,
            original_width=1000, original_height=1001,
            target_aspect_ratio="1:1"
        )
        self.assertEqual(x, 30)
        self.assertEqual(y, 70)

    # ==================== Landscape to Square (Crop Sides) Tests ====================

    def test_landscape_to_square_center_tag(self):
        """Test wide image to 1:1 with tag in center"""
        # 2000x1000 → crop to 1000x1000 (remove 500px from each side)
        # Tag at center (50%, 50%) should remain at center
        x, y = adjust_tag_position_for_center_crop(
            x_percent=50, y_percent=50,
            original_width=2000, original_height=1000,
            target_aspect_ratio="1:1"
        )
        self.assertEqual(x, 50)
        self.assertEqual(y, 50)

    def test_landscape_to_square_left_edge_tag(self):
        """Test wide image with tag near left edge (should be cropped out)"""
        # 2000x1000 → crop to 1000x1000 (remove 500px from each side)
        # Tag at 10% (200px) is within cropped area (< 500px)
        x, y = adjust_tag_position_for_center_crop(
            x_percent=10, y_percent=50,
            original_width=2000, original_height=1000,
            target_aspect_ratio="1:1"
        )
        # 200px - 500px crop = -300px → negative percent (outside visible area)
        self.assertLess(x, 0)
        self.assertEqual(y, 50)

    def test_landscape_to_square_right_edge_tag(self):
        """Test wide image with tag near right edge (should be cropped out)"""
        # 2000x1000 → crop to 1000x1000 (remove 500px from each side)
        # Tag at 90% (1800px) is within right cropped area (> 1500px)
        x, y = adjust_tag_position_for_center_crop(
            x_percent=90, y_percent=50,
            original_width=2000, original_height=1000,
            target_aspect_ratio="1:1"
        )
        # 1800px - 500px crop = 1300px → > 100% of new 1000px width
        self.assertGreater(x, 100)
        self.assertEqual(y, 50)

    def test_landscape_to_square_left_visible_boundary(self):
        """Test tag exactly at left visible boundary after crop"""
        # 2000x1000 → crop to 1000x1000 (remove 500px from each side)
        # Tag at 25% (500px) should be at 0% after crop
        x, y = adjust_tag_position_for_center_crop(
            x_percent=25, y_percent=50,
            original_width=2000, original_height=1000,
            target_aspect_ratio="1:1"
        )
        self.assertAlmostEqual(x, 0, places=5)
        self.assertEqual(y, 50)

    def test_landscape_to_square_right_visible_boundary(self):
        """Test tag exactly at right visible boundary after crop"""
        # 2000x1000 → crop to 1000x1000 (remove 500px from each side)
        # Tag at 75% (1500px) should be at 100% after crop
        x, y = adjust_tag_position_for_center_crop(
            x_percent=75, y_percent=50,
            original_width=2000, original_height=1000,
            target_aspect_ratio="1:1"
        )
        self.assertAlmostEqual(x, 100, places=5)
        self.assertEqual(y, 50)

    def test_landscape_to_square_quarter_positions(self):
        """Test specific quarter positions in wide image"""
        # 3000x1000 → crop to 1000x1000 (remove 1000px from each side)
        # Left quarter: 25% of 3000 = 750px, after crop: (750-1000)/1000 = -25%
        x1, y1 = adjust_tag_position_for_center_crop(
            x_percent=25, y_percent=50,
            original_width=3000, original_height=1000,
            target_aspect_ratio="1:1"
        )
        self.assertAlmostEqual(x1, -25, places=5)
        
        # Right three-quarters: 75% of 3000 = 2250px, after crop: (2250-1000)/1000 = 125%
        x2, y2 = adjust_tag_position_for_center_crop(
            x_percent=75, y_percent=50,
            original_width=3000, original_height=1000,
            target_aspect_ratio="1:1"
        )
        self.assertAlmostEqual(x2, 125, places=5)

    # ==================== Portrait to Square (Crop Top/Bottom) Tests ====================

    def test_portrait_to_square_center_tag(self):
        """Test tall image to 1:1 with tag in center"""
        # 1000x2000 → crop to 1000x1000 (remove 500px from top and bottom)
        # Tag at center (50%, 50%) should remain at center
        x, y = adjust_tag_position_for_center_crop(
            x_percent=50, y_percent=50,
            original_width=1000, original_height=2000,
            target_aspect_ratio="1:1"
        )
        self.assertEqual(x, 50)
        self.assertEqual(y, 50)

    def test_portrait_to_square_top_edge_tag(self):
        """Test tall image with tag near top edge (should be cropped out)"""
        # 1000x2000 → crop to 1000x1000 (remove 500px from top and bottom)
        # Tag at 10% (200px) is within cropped area (< 500px)
        x, y = adjust_tag_position_for_center_crop(
            x_percent=50, y_percent=10,
            original_width=1000, original_height=2000,
            target_aspect_ratio="1:1"
        )
        self.assertEqual(x, 50)
        # 200px - 500px crop = -300px → negative percent
        self.assertLess(y, 0)

    def test_portrait_to_square_bottom_edge_tag(self):
        """Test tall image with tag near bottom edge (should be cropped out)"""
        # 1000x2000 → crop to 1000x1000 (remove 500px from top and bottom)
        # Tag at 90% (1800px) is within bottom cropped area (> 1500px)
        x, y = adjust_tag_position_for_center_crop(
            x_percent=50, y_percent=90,
            original_width=1000, original_height=2000,
            target_aspect_ratio="1:1"
        )
        self.assertEqual(x, 50)
        # 1800px - 500px crop = 1300px → > 100% of new 1000px height
        self.assertGreater(y, 100)

    def test_portrait_to_square_top_visible_boundary(self):
        """Test tag exactly at top visible boundary after crop"""
        # 1000x2000 → crop to 1000x1000 (remove 500px from top and bottom)
        # Tag at 25% (500px) should be at 0% after crop
        x, y = adjust_tag_position_for_center_crop(
            x_percent=50, y_percent=25,
            original_width=1000, original_height=2000,
            target_aspect_ratio="1:1"
        )
        self.assertEqual(x, 50)
        self.assertAlmostEqual(y, 0, places=5)

    def test_portrait_to_square_bottom_visible_boundary(self):
        """Test tag exactly at bottom visible boundary after crop"""
        # 1000x2000 → crop to 1000x1000 (remove 500px from top and bottom)
        # Tag at 75% (1500px) should be at 100% after crop
        x, y = adjust_tag_position_for_center_crop(
            x_percent=50, y_percent=75,
            original_width=1000, original_height=2000,
            target_aspect_ratio="1:1"
        )
        self.assertEqual(x, 50)
        self.assertAlmostEqual(y, 100, places=5)

    # ==================== 4:5 Aspect Ratio Tests ====================

    def test_landscape_to_4_5_crop(self):
        """Test wide image cropped to 4:5 aspect ratio"""
        # 1600x1000 (16:10) → crop to 800x1000 (4:5)
        # Removes 400px from each side
        x, y = adjust_tag_position_for_center_crop(
            x_percent=50, y_percent=50,
            original_width=1600, original_height=1000,
            target_aspect_ratio="4:5"
        )
        self.assertEqual(x, 50)
        self.assertEqual(y, 50)

    def test_portrait_to_4_5_crop(self):
        """Test tall image cropped to 4:5 aspect ratio"""
        # 800x1500 → crop to 800x1000 (4:5)
        # Removes 250px from top and bottom
        x, y = adjust_tag_position_for_center_crop(
            x_percent=50, y_percent=50,
            original_width=800, original_height=1500,
            target_aspect_ratio="4:5"
        )
        self.assertEqual(x, 50)
        self.assertEqual(y, 50)

    def test_4_5_aspect_with_off_center_tag(self):
        """Test 4:5 conversion with tag not at center"""
        # 1000x2000 → crop to 1000x1250 (4:5)
        # Removes 375px from top and bottom
        # Tag at 60% y = 1200px → (1200 - 375) = 825px / 1250 = 66%
        x, y = adjust_tag_position_for_center_crop(
            x_percent=30, y_percent=60,
            original_width=1000, original_height=2000,
            target_aspect_ratio="4:5"
        )
        self.assertEqual(x, 30)
        self.assertAlmostEqual(y, 66, places=5)

    # ==================== Edge Case Tests ====================

    def test_extreme_panorama(self):
        """Test extremely wide panoramic image"""
        # 5000x1000 → crop to 1000x1000
        # Removes 2000px from each side
        x, y = adjust_tag_position_for_center_crop(
            x_percent=50, y_percent=50,
            original_width=5000, original_height=1000,
            target_aspect_ratio="1:1"
        )
        self.assertEqual(x, 50)
        self.assertEqual(y, 50)

    def test_extreme_portrait(self):
        """Test extremely tall portrait image"""
        # 1000x5000 → crop to 1000x1000
        # Removes 2000px from top and bottom
        x, y = adjust_tag_position_for_center_crop(
            x_percent=50, y_percent=50,
            original_width=1000, original_height=5000,
            target_aspect_ratio="1:1"
        )
        self.assertEqual(x, 50)
        self.assertEqual(y, 50)

    def test_corner_positions(self):
        """Test tags in all four corners"""
        # 2000x2000 to 4:5 → crop to 2000x2500 (adds 250px top/bottom conceptually)
        # Actually: 2000x2000 is wider than 4:5, so crops to 1600x2000
        # Removes 200px from left and right
        
        # Top-left corner (0%, 0%)
        x1, y1 = adjust_tag_position_for_center_crop(
            x_percent=0, y_percent=0,
            original_width=2000, original_height=2000,
            target_aspect_ratio="4:5"
        )
        self.assertLess(x1, 0)  # Outside visible area
        self.assertEqual(y1, 0)
        
        # Top-right corner (100%, 0%)
        x2, y2 = adjust_tag_position_for_center_crop(
            x_percent=100, y_percent=0,
            original_width=2000, original_height=2000,
            target_aspect_ratio="4:5"
        )
        self.assertGreater(x2, 100)  # Outside visible area
        self.assertEqual(y2, 0)

    def test_zero_position(self):
        """Test tag at 0,0 position"""
        x, y = adjust_tag_position_for_center_crop(
            x_percent=0, y_percent=0,
            original_width=2000, original_height=1000,
            target_aspect_ratio="1:1"
        )
        # 0px - 500px crop = -500px / 1000px = -50%
        self.assertAlmostEqual(x, -50, places=5)
        self.assertEqual(y, 0)

    def test_100_position(self):
        """Test tag at 100,100 position"""
        x, y = adjust_tag_position_for_center_crop(
            x_percent=100, y_percent=100,
            original_width=2000, original_height=1000,
            target_aspect_ratio="1:1"
        )
        # 2000px - 500px crop = 1500px / 1000px = 150%
        self.assertAlmostEqual(x, 150, places=5)
        self.assertEqual(y, 100)

    def test_small_dimensions(self):
        """Test with very small image dimensions"""
        x, y = adjust_tag_position_for_center_crop(
            x_percent=50, y_percent=50,
            original_width=100, original_height=50,
            target_aspect_ratio="1:1"
        )
        self.assertEqual(x, 50)
        self.assertEqual(y, 50)

    def test_large_dimensions(self):
        """Test with very large image dimensions"""
        x, y = adjust_tag_position_for_center_crop(
            x_percent=50, y_percent=50,
            original_width=10000, original_height=5000,
            target_aspect_ratio="1:1"
        )
        self.assertEqual(x, 50)
        self.assertEqual(y, 50)

    def test_floating_point_inputs(self):
        """Test with floating point percentage inputs"""
        x, y = adjust_tag_position_for_center_crop(
            x_percent=33.333, y_percent=66.667,
            original_width=2000, original_height=1000,
            target_aspect_ratio="1:1"
        )
        # Should handle floats correctly
        self.assertIsInstance(x, float)
        self.assertIsInstance(y, float)

    def test_invalid_aspect_ratio_format(self):
        """Test handling of invalid aspect ratio format"""
        with self.assertRaises(ValueError):
            adjust_tag_position_for_center_crop(
                x_percent=50, y_percent=50,
                original_width=1000, original_height=1000,
                target_aspect_ratio="invalid"
            )

    def test_invalid_aspect_ratio_single_number(self):
        """Test handling of aspect ratio with single number"""
        with self.assertRaises(ValueError):
            adjust_tag_position_for_center_crop(
                x_percent=50, y_percent=50,
                original_width=1000, original_height=1000,
                target_aspect_ratio="1"
            )

    # ==================== Mathematical Precision Tests ====================

    def test_calculation_precision_landscape(self):
        """Test mathematical precision for landscape crop"""
        # 2400x1000 → crop to 1000x1000 (remove 700px each side)
        # Tag at 40% = 960px → (960 - 700) / 1000 = 26%
        x, y = adjust_tag_position_for_center_crop(
            x_percent=40, y_percent=50,
            original_width=2400, original_height=1000,
            target_aspect_ratio="1:1"
        )
        self.assertAlmostEqual(x, 26, places=5)
        self.assertEqual(y, 50)

    def test_calculation_precision_portrait(self):
        """Test mathematical precision for portrait crop"""
        # 1000x2400 → crop to 1000x1000 (remove 700px top/bottom)
        # Tag at 40% = 960px → (960 - 700) / 1000 = 26%
        x, y = adjust_tag_position_for_center_crop(
            x_percent=50, y_percent=40,
            original_width=1000, original_height=2400,
            target_aspect_ratio="1:1"
        )
        self.assertEqual(x, 50)
        self.assertAlmostEqual(y, 26, places=5)

    def test_symmetry(self):
        """Test that equidistant tags from center move symmetrically"""
        # 3000x1000 → crop to 1000x1000
        # Tag at 40% (1200px) and 60% (1800px) should be equidistant from 50%
        x1, _ = adjust_tag_position_for_center_crop(
            x_percent=40, y_percent=50,
            original_width=3000, original_height=1000,
            target_aspect_ratio="1:1"
        )
        x2, _ = adjust_tag_position_for_center_crop(
            x_percent=60, y_percent=50,
            original_width=3000, original_height=1000,
            target_aspect_ratio="1:1"
        )
        # Both should be equidistant from 50%
        self.assertAlmostEqual(abs(x1 - 50), abs(x2 - 50), places=5)

    def test_real_world_scenario_instagram(self):
        """Test realistic Instagram scenario: 1080x1920 portrait to 4:5"""
        # Common phone photo dimensions to Instagram 4:5
        # 1080x1920 → crop to 1080x1350 (remove 285px top/bottom)
        # Tag at 70% y = 1344px → (1344 - 285) / 1350 ≈ 78.44%
        x, y = adjust_tag_position_for_center_crop(
            x_percent=50, y_percent=70,
            original_width=1080, original_height=1920,
            target_aspect_ratio="4:5"
        )
        self.assertEqual(x, 50)
        expected_y = ((0.70 * 1920) - 285) / 1350 * 100
        self.assertAlmostEqual(y, expected_y, places=2)
'''
The data augmentation operations of the original SSD implementation.

Copyright (C) 2018 Pierluigi Ferrari

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

from __future__ import division
import numpy as np
import cv2

from data_generator.object_detection_2d_photometric_ops import ConvertColor, ConvertDataType, ConvertTo3Channels, RandomBrightness, RandomContrast, RandomHue, RandomSaturation, RandomChannelSwap
from data_generator.object_detection_2d_patch_sample_ops import PatchCoordinateGenerator, RandomPatch, RandomPatchInf
from data_generator.object_detection_2d_geometric_ops import ResizeRandomInterp, RandomFlip
from data_generator.object_detection_2d_image_boxes_validation_utils import BoundGenerator, BoxFilter, ImageValidator

class SSDRandomCrop:
    '''
    Performs the same random crops as defined by the `batch_sampler` instructions
    of the original Caffe implementation of SSD. A description of this random cropping
    strategy can also be found in the data augmentation section of the paper:
    https://arxiv.org/abs/1512.02325
    '''

    def __init__(self):

        # This randomly samples one of the lower IoU bounds defined
        # by the `sample_space` every time it is called.
        self.bound_generator = BoundGenerator(sample_space=((None, None),
                                                            (0.1, None),
                                                            (0.3, None),
                                                            (0.5, None),
                                                            (0.7, None),
                                                            (0.9, None)),
                                              weights=None)

        # Produces coordinates for candidate patches such that the height
        # and width of the patches are between 0.3 and 1.0 of the height
        # and width of the respective image and the aspect ratio of the
        # patches is between 0.5 and 2.0.
        self.patch_coord_generator = PatchCoordinateGenerator(must_match='h_w',
                                                              min_scale=0.3,
                                                              max_scale=1.0,
                                                              scale_uniformly=False,
                                                              min_aspect_ratio = 0.5,
                                                              max_aspect_ratio = 2.0)

        # Filters out boxes whose center point does not lie within the
        # chosen patches.
        self.box_filter = BoxFilter(overlap_criterion='center_point')

        # Determines whether a given patch is considered a valid patch.
        # Defines a patch to be valid if at least one ground truth bounding box
        # (n_boxes_min == 1) has an IoU overlap with the patch that
        # meets the requirements defined by `bound_generator`.
        self.image_validator = ImageValidator(overlap_criterion='iou',
                                              n_boxes_min=1)

        # Performs crops according to the parameters set in the objects above.
        # Runs until either a valid patch is found or the original input image
        # is returned unaltered. Runs a maximum of 50 trials to find a valid
        # patch for each new sampled IoU threshold. Every 50 trials, the original
        # image is returned as is with probability (1 - prob) = 0.143.
        # Does not clip the ground truth bounding boxes to lie within the patch.
        self.random_crop = RandomPatchInf(patch_coord_generator=self.patch_coord_generator,
                                          box_filter=self.box_filter,
                                          image_validator=self.image_validator,
                                          bound_generator=self.bound_generator,
                                          n_trials_max=50,
                                          clip_boxes=False,
                                          prob=0.857)

    def __call__(self, image, labels=None):
        return self.random_crop(image, labels)

class SSDExpand:
    '''
    Performs the random image expansion as defined by the `train_transform_param` instructions
    of the original Caffe implementation of SSD. A description of this expansion strategy
    can also be found in section 3.6 ("Data Augmentation for Small Object Accuracy") of the paper:
    https://arxiv.org/abs/1512.02325
    '''

    def __init__(self, background=(123, 117, 104)):

        # Generate coordinates for patches that are between 1.0 and 4.0 times
        # the size of the input image in both spatial dimensions.
        self.patch_coord_generator = PatchCoordinateGenerator(must_match='h_w',
                                                              min_scale=1.0,
                                                              max_scale=4.0,
                                                              scale_uniformly=True)

        # With probability 0.5, place the input image randomly on a canvas filled with
        # mean color values according to the parameters set above. With probability 0.5,
        # return the input image unaltered.
        self.expand = RandomPatch(patch_coord_generator=self.patch_coord_generator,
                                  box_filter=None,
                                  image_validator=None,
                                  n_trials_max=1,
                                  clip_boxes=False,
                                  prob=0.5,
                                  background=background)

    def __call__(self, image, labels=None):
        return self.expand(image, labels)

class SSDPhotometricDistortions:
    '''
    Performs the photometric distortions defined by the `train_transform_param` instructions
    of the original Caffe implementation of SSD.
    '''

    def __init__(self):

        self.convert_RGB_to_HSV = ConvertColor(current='RGB', to='HSV')
        self.convert_HSV_to_RGB = ConvertColor(current='HSV', to='RGB')
        self.convert_to_float32 = ConvertDataType(to='float32')
        self.convert_to_uint8 = ConvertDataType(to='uint8')
        self.convert_to_3_channels = ConvertTo3Channels()
        self.random_brightness = RandomBrightness(lower=-32, upper=32, prob=0.5)
        self.random_contrast = RandomContrast(lower=0.5, upper=1.5, prob=0.5)
        self.random_saturation = RandomSaturation(lower=0.5, upper=1.5, prob=0.5)
        self.random_hue = RandomHue(max_delta=18, prob=0.5)
        self.random_channel_swap = RandomChannelSwap(prob=0.0)

        self.sequence1 = [self.convert_to_3_channels,
                          self.convert_to_float32,
                          self.random_brightness,
                          self.random_contrast,
                          self.convert_to_uint8,
                          self.convert_RGB_to_HSV,
                          self.convert_to_float32,
                          self.random_saturation,
                          self.random_hue,
                          self.convert_to_uint8,
                          self.convert_HSV_to_RGB,
                          self.random_channel_swap]

        self.sequence2 = [self.convert_to_3_channels,
                          self.convert_to_float32,
                          self.random_brightness,
                          self.convert_to_uint8,
                          self.convert_RGB_to_HSV,
                          self.convert_to_float32,
                          self.random_saturation,
                          self.random_hue,
                          self.convert_to_uint8,
                          self.convert_HSV_to_RGB,
                          self.convert_to_float32,
                          self.random_contrast,
                          self.convert_to_uint8,
                          self.random_channel_swap]

    def __call__(self, image, labels):

        # Choose sequence 1 with probability 0.5.
        if np.random.choice(2):

            for transform in self.sequence1:
                image, labels = transform(image, labels)
            return image, labels
        # Choose sequence 2 with probability 0.5.
        else:

            for transform in self.sequence2:
                image, labels = transform(image, labels)
            return image, labels

class SSDDataAugmentation:
    '''
    Reproduces the data augmentation pipeline used in the training of the original
    Caffe implementation of SSD.
    '''

    def __init__(self, img_height=300, img_width=300, background=(123, 117, 104)):

        self.photometric_distortions = SSDPhotometricDistortions()
        self.expand = SSDExpand(background=background)
        self.random_crop = SSDRandomCrop()
        self.random_flip = RandomFlip(dim='horizontal', prob=0.5)
        self.resize = ResizeRandomInterp(height=img_height,
                                         width=img_width,
                                         interpolation_modes=[cv2.INTER_NEAREST,
                                                              cv2.INTER_LINEAR,
                                                              cv2.INTER_CUBIC,
                                                              cv2.INTER_AREA,
                                                              cv2.INTER_LANCZOS4])

        self.sequence = [self.photometric_distortions,
                         self.expand,
                         self.random_crop,
                         self.random_flip,
                         self.resize]

    def __call__(self, image, labels):

        for transform in self.sequence:
            image, labels = transform(image, labels)
        return image, labels